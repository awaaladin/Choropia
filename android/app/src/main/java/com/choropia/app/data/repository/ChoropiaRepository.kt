package com.choropia.app.data.repository

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import com.choropia.app.data.TokenManager
import com.choropia.app.data.model.AppNotification
import com.choropia.app.data.model.Category
import com.choropia.app.data.model.Comment
import com.choropia.app.data.model.Conversation
import com.choropia.app.data.model.Listing
import com.choropia.app.data.model.Merchant
import com.choropia.app.data.model.MerchantApplication
import com.choropia.app.data.model.Message
import com.choropia.app.data.model.Order
import com.choropia.app.data.model.PaymentInitResponse
import com.choropia.app.data.model.PaymentVerifyResponse
import com.choropia.app.data.model.Review
import com.choropia.app.data.model.TwoFactorConfirmed
import com.choropia.app.data.model.TwoFactorSetup
import com.choropia.app.data.model.TwoFactorStatus
import com.choropia.app.data.model.User
import com.choropia.app.data.network.TwoFactorCodeRequest
import com.choropia.app.data.network.TwoFactorDisableRequest
import com.choropia.app.data.network.TwoFactorVerifyRequest
import com.choropia.app.data.network.ApiException
import com.choropia.app.data.network.ChoropiaApi
import com.choropia.app.data.network.CreateCommentRequest
import com.choropia.app.data.network.CreateConversationRequest
import com.choropia.app.data.network.CreateFollowRequest
import com.choropia.app.data.network.CreateLikeRequest
import com.choropia.app.data.network.CreateMerchantApplicationRequest
import com.choropia.app.data.network.CreateOrderRequest
import com.choropia.app.data.network.CreateReportRequest
import com.choropia.app.data.network.CreateReviewRequest
import com.choropia.app.data.network.DisputeRequest
import com.choropia.app.data.network.InitializePaymentRequest
import com.choropia.app.data.network.LoginRequest
import com.choropia.app.data.network.LogoutRequest
import com.choropia.app.data.network.PasswordResetConfirmRequest
import com.choropia.app.data.network.PasswordResetRequest
import com.choropia.app.data.network.ProfileUpdate
import com.choropia.app.data.network.RegisterRequest
import com.choropia.app.data.network.SendMessageRequest
import com.choropia.app.data.network.UpdateProfileRequest
import com.choropia.app.data.network.apiCall
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.ByteArrayOutputStream

/** Result of the first login step. */
sealed interface LoginResult {
    data class Success(val user: User) : LoginResult
    /** The account has 2-step verification on: ask for a code, then call [ChoropiaRepository.verifyTwoFactor]. */
    data class NeedsCode(val challenge: String) : LoginResult
}

/** Filters for the marketplace browse screen. */
data class ListingQuery(
    val search: String? = null,
    val categorySlug: String? = null,
    val condition: String? = null,
    val ordering: String? = null,
    val minPrice: String? = null,
    val maxPrice: String? = null,
    val merchantId: Int? = null,
    /** Only the signed-in user's own listings (including sold ones). */
    val mine: Boolean? = null,
)

/**
 * The single place screens talk to. Wraps every Retrofit call in [apiCall] (so failures arrive as
 * human-readable [ApiException]s), keeps token persistence out of the UI, and caches the
 * like/follow row ids that the backend needs for un-liking / un-following.
 */
class ChoropiaRepository(
    private val appContext: Context,
    private val api: ChoropiaApi,
    private val tokenManager: TokenManager,
) {
    val isLoggedInFlow = tokenManager.isLoggedInFlow
    val themeModeFlow = tokenManager.themeModeFlow
    val savedIdsFlow = tokenManager.savedIdsFlow

    suspend fun toggleSaved(listingId: Int) = tokenManager.toggleSaved(listingId)

    /** Fetches the bookmarked listings; ones that were deleted or failed are skipped. */
    suspend fun savedListings(ids: Set<Int>): List<Listing> = coroutineScope {
        ids.map { id -> async { runCatching { api.getListing(id) }.getOrNull() } }.awaitAll().filterNotNull()
    }

    suspend fun setThemeMode(mode: String) = tokenManager.setThemeMode(mode)
    suspend fun isLoggedIn(): Boolean = tokenManager.getRefreshToken() != null
    suspend fun accessTokenOrNull(): String? = tokenManager.getAccessToken()

    // --- auth ---------------------------------------------------------------------------------

    suspend fun login(identifier: String, password: String): LoginResult = apiCall {
        val response = api.login(LoginRequest(identifier.trim(), password))
        val challenge = response.challenge
        if (response.two_factor_required && challenge != null) {
            LoginResult.NeedsCode(challenge)
        } else {
            val access = response.access
            val refresh = response.refresh
            val user = response.user
            if (access == null || refresh == null || user == null) throw ApiException("Unexpected login response.")
            tokenManager.saveTokens(access, refresh)
            clearCaches()
            LoginResult.Success(user)
        }
    }

    suspend fun verifyTwoFactor(challenge: String, code: String): User = apiCall {
        val response = api.verifyTwoFactor(TwoFactorVerifyRequest(challenge, code.trim()))
        tokenManager.saveTokens(response.access, response.refresh)
        clearCaches()
        response.user
    }

    suspend fun twoFactorStatus(): TwoFactorStatus = apiCall { api.twoFactorStatus() }
    suspend fun twoFactorSetup(): TwoFactorSetup = apiCall { api.twoFactorSetup() }
    suspend fun twoFactorConfirm(code: String): TwoFactorConfirmed =
        apiCall { api.twoFactorConfirm(TwoFactorCodeRequest(code.trim())) }
    suspend fun twoFactorDisable(password: String, code: String) =
        apiCall { api.twoFactorDisable(TwoFactorDisableRequest(password, code.trim())) }

    suspend fun register(
        email: String,
        password: String,
        phone: String?,
        firstName: String,
        lastName: String,
    ): User = apiCall {
        val response = api.register(
            RegisterRequest(email.trim(), password, phone?.trim()?.ifBlank { null }, firstName.trim(), lastName.trim(), accept_terms = true)
        )
        tokenManager.saveTokens(response.access, response.refresh)
        clearCaches()
        response.user
    }

    suspend fun logout() {
        val refresh = tokenManager.getRefreshToken()
        if (refresh != null) runCatching { api.logout(LogoutRequest(refresh)) }
        tokenManager.clear()
        clearCaches()
    }

    suspend fun requestPasswordReset(email: String) = apiCall { api.requestPasswordReset(PasswordResetRequest(email.trim())) }

    suspend fun confirmPasswordReset(uid: String, token: String, password: String) =
        apiCall { api.confirmPasswordReset(PasswordResetConfirmRequest(uid.trim(), token.trim(), password)) }

    suspend fun me(): User = apiCall { api.me() }

    suspend fun updateProfile(
        firstName: String,
        lastName: String,
        phoneNumber: String?,
        bio: String,
        location: String,
        themePreference: String,
    ): User = apiCall {
        api.updateProfile(
            UpdateProfileRequest(
                firstName.trim(), lastName.trim(), phoneNumber?.trim()?.ifBlank { null },
                ProfileUpdate(bio.trim(), location.trim(), themePreference),
            )
        )
    }

    // --- listings -----------------------------------------------------------------------------

    data class Page<T>(val items: List<T>, val next: String?)

    suspend fun feed(): Page<Listing> = apiCall { api.feed().let { Page(it.results, it.next) } }

    suspend fun listings(query: ListingQuery = ListingQuery()): Page<Listing> = apiCall {
        api.listListings(
            categorySlug = query.categorySlug,
            search = query.search?.trim()?.ifBlank { null },
            ordering = query.ordering,
            condition = query.condition,
            minPrice = query.minPrice,
            maxPrice = query.maxPrice,
            merchantId = query.merchantId,
            mine = query.mine,
        ).let { Page(it.results, it.next) }
    }

    suspend fun listingsPage(url: String): Page<Listing> = apiCall { api.listingsPage(url).let { Page(it.results, it.next) } }

    suspend fun getListing(id: Int): Listing = apiCall { api.getListing(id) }

    suspend fun categories(): List<Category> = apiCall { api.listCategories() }

    /**
     * Posts a listing as multipart. Photos are downscaled + re-encoded on the device first:
     * the server sits behind Vercel, which rejects request bodies over ~4.5 MB, and phone-camera
     * originals are routinely 4–8 MB each.
     */
    suspend fun createListing(
        title: String,
        description: String,
        price: String,
        condition: String,
        categoryId: Int,
        location: String,
        photoUris: List<Uri>,
    ): Listing {
        val parts = withContext(Dispatchers.IO) {
            photoUris.take(MAX_PHOTOS).mapIndexed { index, uri ->
                val bytes = compressImage(uri)
                MultipartBody.Part.createFormData(
                    "uploaded_photos",
                    "photo_$index.jpg",
                    bytes.toRequestBody("image/jpeg".toMediaType()),
                )
            }
        }
        val text = "text/plain".toMediaType()
        fun field(value: String): RequestBody = value.toRequestBody(text)
        val fields = buildMap<String, RequestBody> {
            put("title", field(title.trim()))
            put("description", field(description.trim()))
            put("price", field(price.trim()))
            put("condition", field(condition))
            put("category", field(categoryId.toString()))
            if (location.isNotBlank()) put("location", field(location.trim()))
        }
        return apiCall { api.createListing(fields, parts) }
    }

    suspend fun markSold(listingId: Int): Listing = apiCall { api.markSold(listingId) }

    private fun compressImage(uri: Uri): ByteArray {
        val resolver = appContext.contentResolver
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        resolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, bounds) }
        var sample = 1
        while (bounds.outWidth / sample > MAX_EDGE * 2 || bounds.outHeight / sample > MAX_EDGE * 2) sample *= 2

        val decoded = resolver.openInputStream(uri)?.use {
            BitmapFactory.decodeStream(it, null, BitmapFactory.Options().apply { inSampleSize = sample })
        } ?: throw ApiException("Couldn't read one of the selected photos.")

        val scale = minOf(1f, MAX_EDGE.toFloat() / maxOf(decoded.width, decoded.height))
        val scaled = if (scale < 1f) {
            Bitmap.createScaledBitmap(decoded, (decoded.width * scale).toInt(), (decoded.height * scale).toInt(), true)
        } else decoded

        val out = ByteArrayOutputStream()
        var quality = 82
        do {
            out.reset()
            scaled.compress(Bitmap.CompressFormat.JPEG, quality, out)
            quality -= 8
        } while (out.size() > MAX_PHOTO_BYTES && quality > 40)
        if (scaled !== decoded) decoded.recycle()
        scaled.recycle()
        return out.toByteArray()
    }

    // --- likes / follows (id caches) ----------------------------------------------------------

    private var likeIds: MutableMap<Int, Int>? = null          // listingId -> likeId
    private var followIds: MutableMap<String, Int>? = null     // "user:5" / "merchant:2" -> followId

    private fun clearCaches() {
        likeIds = null
        followIds = null
    }

    private suspend fun likeMap(): MutableMap<Int, Int> {
        likeIds?.let { return it }
        val map = mutableMapOf<Int, Int>()
        var page = apiCall { api.listMyLikes() }
        while (true) {
            page.results.forEach { map[it.listing] = it.id }
            val next = page.next ?: break
            page = apiCall { api.likesPage(next) }
        }
        likeIds = map
        return map
    }

    /** Likes or un-likes; returns the new liked state. */
    suspend fun setLiked(listingId: Int, liked: Boolean): Boolean {
        val map = likeMap()
        if (liked) {
            if (listingId !in map) {
                val like = apiCall { api.likeListing(CreateLikeRequest(listingId)) }
                map[listingId] = like.id
            }
        } else {
            map[listingId]?.let { id ->
                apiCall { api.unlikeListing(id) }
                map.remove(listingId)
            }
        }
        return liked
    }

    private suspend fun followMap(): MutableMap<String, Int> {
        followIds?.let { return it }
        val map = mutableMapOf<String, Int>()
        var page = apiCall { api.listMyFollows() }
        while (true) {
            page.results.forEach { map["${it.target_type_display}:${it.object_id}"] = it.id }
            val next = page.next ?: break
            page = apiCall { api.followsPage(next) }
        }
        followIds = map
        return map
    }

    suspend fun isFollowing(targetType: String, targetId: Int): Boolean = "$targetType:$targetId" in followMap()

    suspend fun setFollowing(targetType: String, targetId: Int, following: Boolean) {
        val map = followMap()
        val key = "$targetType:$targetId"
        if (following) {
            if (key !in map) map[key] = apiCall { api.follow(CreateFollowRequest(targetType, targetId)) }.id
        } else {
            map[key]?.let { id ->
                apiCall { api.unfollow(id) }
                map.remove(key)
            }
        }
    }

    // --- comments -----------------------------------------------------------------------------

    suspend fun comments(listingId: Int): List<Comment> = apiCall { api.listComments(listingId).results }

    suspend fun addComment(listingId: Int, body: String, parentId: Int? = null): Comment =
        apiCall { api.createComment(CreateCommentRequest(listingId, body.trim(), parentId)) }

    // --- chat ---------------------------------------------------------------------------------

    suspend fun conversations(): List<Conversation> = apiCall { api.listConversations().results }

    suspend fun conversation(id: Int): Conversation = apiCall { api.getConversation(id) }

    suspend fun startConversation(listingId: Int): Conversation =
        apiCall { api.startConversation(CreateConversationRequest(listingId)) }

    /** Messages come back newest-last from the API; pages are followed so long threads are whole. */
    suspend fun messages(conversationId: Int): List<Message> = apiCall {
        val all = mutableListOf<Message>()
        var page = api.getMessages(conversationId)
        var guard = 0
        while (true) {
            all += page.results
            val next = page.next ?: break
            if (++guard > 20) break
            page = api.messagesPage(next)
        }
        all
    }

    suspend fun sendMessage(conversationId: Int, body: String): Message =
        apiCall { api.sendMessage(SendMessageRequest(conversationId, body.trim())) }

    /** Sends a photo (compressed on-device first) as a chat attachment. */
    suspend fun sendImage(conversationId: Int, uri: Uri, caption: String = ""): Message {
        val bytes = withContext(Dispatchers.IO) { compressImage(uri) }
        val part = MultipartBody.Part.createFormData(
            "attachment", "photo.jpg", bytes.toRequestBody("image/jpeg".toMediaType()),
        )
        return sendAttachmentPart(conversationId, caption, null, part)
    }

    /** Sends a recorded voice note (m4a/AAC). */
    suspend fun sendVoiceNote(conversationId: Int, file: java.io.File, durationSeconds: Int): Message {
        val bytes = withContext(Dispatchers.IO) { file.readBytes() }
        val part = MultipartBody.Part.createFormData(
            "attachment", "voice.m4a", bytes.toRequestBody("audio/mp4".toMediaType()),
        )
        return sendAttachmentPart(conversationId, "", durationSeconds, part)
    }

    private suspend fun sendAttachmentPart(
        conversationId: Int,
        body: String,
        durationSeconds: Int?,
        part: MultipartBody.Part,
    ): Message {
        val text = "text/plain".toMediaType()
        return apiCall {
            api.sendAttachment(
                conversationId.toString().toRequestBody(text),
                body.trim().toRequestBody(text),
                durationSeconds?.toString()?.toRequestBody(text),
                part,
            )
        }
    }

    // --- orders & payments --------------------------------------------------------------------

    suspend fun orders(): List<Order> = apiCall { api.listOrders().results }

    suspend fun order(id: Int): Order = apiCall { api.getOrder(id) }

    suspend fun createOrder(listingId: Int): Order = apiCall { api.createOrder(CreateOrderRequest(listingId)) }

    suspend fun confirmReceipt(orderId: Int): Order = apiCall { api.confirmReceipt(orderId) }

    suspend fun openDispute(orderId: Int, reason: String): Order =
        apiCall { api.openDispute(orderId, DisputeRequest(reason.trim())) }

    suspend fun assignCourier(orderId: Int): Order = apiCall { api.assignCourier(orderId) }

    suspend fun markInTransit(orderId: Int): Order = apiCall { api.markInTransit(orderId) }

    suspend fun markDelivered(orderId: Int): Order = apiCall { api.markDelivered(orderId) }

    suspend fun commissionPreview(price: String): com.choropia.app.data.model.CommissionPreview =
        apiCall { api.commissionPreview(price) }

    suspend fun initializePayment(orderId: Int): PaymentInitResponse =
        apiCall { api.initializePayment(InitializePaymentRequest(orderId)) }

    /** Asks the server to check the order's payment with Paystack (no-op for other providers). */
    suspend fun verifyPayment(orderId: Int): PaymentVerifyResponse =
        apiCall { api.verifyPayment(InitializePaymentRequest(orderId)) }

    // --- merchants ----------------------------------------------------------------------------

    suspend fun merchant(id: Int): Merchant = apiCall { api.getMerchant(id) }

    // --- seller payouts ---------------------------------------------------------------------

    suspend fun banks(): List<com.choropia.app.data.model.Bank> = apiCall { api.listBanks() }

    suspend fun payoutAccount(): com.choropia.app.data.model.PayoutAccount = apiCall { api.getPayoutAccount() }

    suspend fun savePayoutAccount(bankCode: String, accountNumber: String): com.choropia.app.data.model.PayoutAccount =
        apiCall { api.savePayoutAccount(com.choropia.app.data.network.PayoutAccountRequest(bankCode, accountNumber)) }

    suspend fun deletePayoutAccount() = apiCall { api.deletePayoutAccount() }

    suspend fun applyForMerchant(
        businessName: String,
        description: String,
        phone: String,
        address: String,
    ): MerchantApplication = apiCall {
        api.applyForMerchant(
            CreateMerchantApplicationRequest(businessName.trim(), description.trim(), phone.trim(), address.trim())
        )
    }

    // --- notifications / reviews / reports ----------------------------------------------------

    suspend fun notifications(): List<AppNotification> = apiCall { api.listNotifications().results }

    suspend fun markNotificationRead(id: Int) = apiCall { api.markNotificationRead(id) }

    suspend fun markAllNotificationsRead() = apiCall { api.markAllNotificationsRead() }

    suspend fun reviewsFor(userId: Int): List<Review> = apiCall { api.listReviewsFor(userId).results }

    suspend fun createReview(orderId: Int, rating: Int, comment: String): Review =
        apiCall { api.createReview(CreateReviewRequest(orderId, rating, comment.trim())) }

    suspend fun reportListing(listingId: Int, reason: String) =
        apiCall { api.report(CreateReportRequest("listing", listingId, reason.trim())) }

    // --- dispatch (delivery drivers) -----------------------------------------------------------

    suspend fun areas(): List<com.choropia.app.data.model.Area> = apiCall { api.listAreas() }

    suspend fun addArea(name: String): com.choropia.app.data.model.Area = apiCall {
        val added = api.addArea(com.choropia.app.data.network.AddAreaRequest(name.trim()))
        com.choropia.app.data.model.Area(added.id, added.name)
    }

    suspend fun driverMe(): com.choropia.app.data.model.DriverMe? = apiCall { api.driverMe() }

    suspend fun driverApply(request: com.choropia.app.data.network.DriverApplyRequest) = apiCall { api.driverApply(request) }

    suspend fun driverAvailability(available: Boolean) =
        apiCall { api.driverAvailability(com.choropia.app.data.network.DriverAvailabilityRequest(available)) }

    /** Identity documents: photos are shrunk on the phone and sent over HTTPS; the server encrypts them before storing. */
    suspend fun uploadDriverDocument(kind: String, uri: Uri): com.choropia.app.data.model.DriverMe {
        val bytes = withContext(Dispatchers.IO) { compressImage(uri) }
        val part = MultipartBody.Part.createFormData("file", "$kind.jpg", bytes.toRequestBody("image/jpeg".toMediaType()))
        return apiCall { api.uploadDriverDocument(kind.toRequestBody("text/plain".toMediaType()), part) }
    }

    suspend fun driverRoutes() = apiCall { api.driverRoutes() }

    suspend fun addDriverRoute(from: Int, to: Int, price: String) =
        apiCall { api.addDriverRoute(com.choropia.app.data.network.AddRouteRequest(from, to, price.trim())) }

    suspend fun deleteDriverRoute(id: Int) = apiCall { api.deleteDriverRoute(id) }

    suspend fun driverJobs() = apiCall { api.driverJobs() }

    suspend fun acceptJob(id: Int) = apiCall { api.acceptJob(id) }

    suspend fun declineJob(id: Int) = apiCall { api.declineJob(id) }

    suspend fun pickupJob(id: Int) = apiCall { api.pickupJob(id) }

    suspend fun deliverJob(id: Int, code: String, photo: Uri): com.choropia.app.data.model.OrderDelivery {
        val bytes = withContext(Dispatchers.IO) { compressImage(photo) }
        val part = MultipartBody.Part.createFormData("photo", "proof.jpg", bytes.toRequestBody("image/jpeg".toMediaType()))
        return apiCall { api.deliverJob(id, code.trim().toRequestBody("text/plain".toMediaType()), part) }
    }

    suspend fun browseDrivers(fromArea: Int) = apiCall { api.browseDrivers(fromArea) }

    suspend fun listingDelivery(listingId: Int, to: Int? = null) = apiCall { api.listingDelivery(listingId, to) }

    suspend fun saveListingDelivery(listingId: Int, enabled: Boolean, payer: String, pickupArea: Int, drivers: List<Int>) =
        apiCall { api.saveListingDelivery(listingId, com.choropia.app.data.network.ListingDeliveryRequest(enabled, payer, pickupArea, drivers)) }

    suspend fun orderDelivery(orderId: Int) = apiCall { api.orderDelivery(orderId) }

    suspend fun chooseDelivery(orderId: Int, dropoffArea: Int, driver: Int, note: String) =
        apiCall { api.chooseDelivery(orderId, com.choropia.app.data.network.ChooseDeliveryRequest(dropoffArea, driver, note.trim())) }

    suspend fun clearDelivery(orderId: Int) = apiCall { api.clearDelivery(orderId) }

    suspend fun reassignDelivery(orderId: Int) = apiCall { api.reassignDelivery(orderId) }

    private companion object {
        const val MAX_PHOTOS = 6
        const val MAX_EDGE = 1600
        const val MAX_PHOTO_BYTES = 600_000
    }
}
