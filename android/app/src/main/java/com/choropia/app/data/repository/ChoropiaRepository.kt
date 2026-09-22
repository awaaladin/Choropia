package com.choropia.app.data.repository

import com.choropia.app.data.TokenManager
import com.choropia.app.data.network.ChoropiaApi
import com.choropia.app.data.network.CreateCommentRequest
import com.choropia.app.data.network.CreateConversationRequest
import com.choropia.app.data.network.CreateFollowRequest
import com.choropia.app.data.network.CreateLikeRequest
import com.choropia.app.data.network.CreateListingRequest
import com.choropia.app.data.network.CreateMerchantApplicationRequest
import com.choropia.app.data.network.CreateOrderRequest
import com.choropia.app.data.network.CreateReportRequest
import com.choropia.app.data.network.CreateReviewRequest
import com.choropia.app.data.network.DisputeRequest
import com.choropia.app.data.network.InitializePaymentRequest
import com.choropia.app.data.network.LoginRequest
import com.choropia.app.data.network.LogoutRequest
import com.choropia.app.data.network.ProfileUpdate
import com.choropia.app.data.network.RegisterRequest
import com.choropia.app.data.network.SendMessageRequest
import com.choropia.app.data.network.UpdateProfileRequest
import com.choropia.app.data.model.Category
import com.choropia.app.data.model.Comment
import com.choropia.app.data.model.Conversation
import com.choropia.app.data.model.Follow
import com.choropia.app.data.model.Like
import com.choropia.app.data.model.Listing
import com.choropia.app.data.model.Merchant
import com.choropia.app.data.model.MerchantApplication
import com.choropia.app.data.model.Message
import com.choropia.app.data.model.Notification
import com.choropia.app.data.model.Order
import com.choropia.app.data.model.PaymentInitResponse
import com.choropia.app.data.model.Review
import com.choropia.app.data.model.User

/** One thin layer over the generated Retrofit API, so ViewModels don't touch request/response
 * DTOs directly and token persistence happens in exactly one place. */
class ChoropiaRepository(private val api: ChoropiaApi, private val tokenManager: TokenManager) {

    val isLoggedInFlow = tokenManager.isLoggedInFlow

    suspend fun login(identifier: String, password: String): User {
        val response = api.login(LoginRequest(identifier, password))
        tokenManager.saveTokens(response.access, response.refresh)
        return response.user
    }

    suspend fun register(email: String, password: String, phone: String?, firstName: String, lastName: String): User {
        val response = api.register(RegisterRequest(email, password, phone, firstName, lastName))
        tokenManager.saveTokens(response.access, response.refresh)
        return response.user
    }

    suspend fun logout() {
        val refresh = tokenManager.getRefreshToken()
        if (refresh != null) runCatching { api.logout(LogoutRequest(refresh)) }
        tokenManager.clear()
    }

    suspend fun me(): User = api.me()

    suspend fun feedOrListings(loggedIn: Boolean): List<Listing> =
        if (loggedIn) api.feed().results else api.listListings().results

    suspend fun listListings(category: String? = null): List<Listing> = api.listListings(category).results

    suspend fun getListing(id: Int): Listing = api.getListing(id)

    suspend fun listConversations(): List<Conversation> = api.listConversations().results

    suspend fun startConversation(listingId: Int): Conversation =
        api.startConversation(CreateConversationRequest(listingId))

    suspend fun getMessages(conversationId: Int): List<Message> = api.getMessages(conversationId).results

    suspend fun sendMessage(conversationId: Int, body: String): Message =
        api.sendMessage(SendMessageRequest(conversationId, body))

    suspend fun listOrders(): List<Order> = api.listOrders().results

    suspend fun createOrder(listingId: Int): Order = api.createOrder(CreateOrderRequest(listingId))

    suspend fun confirmReceipt(orderId: Int): Order = api.confirmReceipt(orderId)

    suspend fun openDispute(orderId: Int, reason: String): Order = api.openDispute(orderId, DisputeRequest(reason))

    suspend fun assignCourier(orderId: Int): Order = api.assignCourier(orderId)

    suspend fun getOrder(orderId: Int): Order = api.getOrder(orderId)

    suspend fun initializePayment(orderId: Int): PaymentInitResponse =
        api.initializePayment(InitializePaymentRequest(orderId))

    suspend fun listCategories(): List<Category> = api.listCategories()

    suspend fun createListing(
        title: String,
        description: String,
        price: String,
        condition: String,
        categoryId: Int,
        location: String,
    ): Listing = api.createListing(CreateListingRequest(title, description, price, condition, categoryId, location))

    suspend fun getMerchant(id: Int): Merchant = api.getMerchant(id)

    suspend fun listMerchantListings(merchantId: Int): List<Listing> = api.listMerchantListings(merchantId).results

    suspend fun listNotifications(): List<Notification> = api.listNotifications().results

    suspend fun markNotificationRead(id: Int): Notification = api.markNotificationRead(id)

    suspend fun markAllNotificationsRead() = api.markAllNotificationsRead()

    suspend fun updateProfile(
        firstName: String,
        lastName: String,
        phoneNumber: String?,
        bio: String,
        location: String,
        themePreference: String,
    ): User = api.updateProfile(
        UpdateProfileRequest(firstName, lastName, phoneNumber, ProfileUpdate(bio, location, themePreference))
    )

    suspend fun listComments(listingId: Int): List<Comment> = api.listComments(listingId).results

    suspend fun createComment(listingId: Int, body: String): Comment =
        api.createComment(CreateCommentRequest(listingId, body))

    suspend fun listMyLikes(): List<Like> = api.listMyLikes().results

    suspend fun likeListing(listingId: Int): Like = api.likeListing(CreateLikeRequest(listingId))

    suspend fun unlikeListing(likeId: Int) = api.unlikeListing(likeId)

    suspend fun listMyFollows(): List<Follow> = api.listMyFollows().results

    suspend fun follow(targetType: String, targetId: Int): Follow =
        api.follow(CreateFollowRequest(targetType, targetId))

    suspend fun unfollow(followId: Int) = api.unfollow(followId)

    suspend fun applyForMerchant(
        businessName: String,
        businessDescription: String,
        businessPhone: String,
        businessAddress: String,
    ): MerchantApplication = api.applyForMerchant(
        CreateMerchantApplicationRequest(businessName, businessDescription, businessPhone, businessAddress)
    )

    suspend fun listReviewsFor(userId: Int): List<Review> = api.listReviewsFor(userId).results

    suspend fun createReview(orderId: Int, rating: Int, comment: String): Review =
        api.createReview(CreateReviewRequest(orderId, rating, comment))

    suspend fun reportListing(listingId: Int, reason: String) =
        api.reportListing(CreateReportRequest("listing", listingId, reason))

    suspend fun getAccessTokenOrNull(): String? = tokenManager.getAccessToken()
}
