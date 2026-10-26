package com.choropia.app.data.network

import com.choropia.app.data.model.AppNotification
import com.choropia.app.data.model.AuthResponse
import com.choropia.app.data.model.Bank
import com.choropia.app.data.model.CommissionPreview
import com.choropia.app.data.model.Category
import com.choropia.app.data.model.PayoutAccount
import com.choropia.app.data.model.Comment
import com.choropia.app.data.model.Conversation
import com.choropia.app.data.model.Follow
import com.choropia.app.data.model.Like
import com.choropia.app.data.model.LoginResponse
import com.choropia.app.data.model.TwoFactorConfirmed
import com.choropia.app.data.model.TwoFactorSetup
import com.choropia.app.data.model.TwoFactorStatus
import com.choropia.app.data.model.Listing
import com.choropia.app.data.model.Merchant
import com.choropia.app.data.model.MerchantApplication
import com.choropia.app.data.model.Message
import com.choropia.app.data.model.Order
import com.choropia.app.data.model.PaginatedResponse
import com.choropia.app.data.model.PaymentInitResponse
import com.choropia.app.data.model.PaymentVerifyResponse
import com.choropia.app.data.model.RefreshResponse
import com.choropia.app.data.model.Report
import com.choropia.app.data.model.Review
import com.choropia.app.data.model.User
import kotlinx.serialization.Serializable
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Part
import retrofit2.http.PartMap
import retrofit2.http.Path
import retrofit2.http.Query
import retrofit2.http.Url

@Serializable data class LoginRequest(val identifier: String, val password: String)

@Serializable
data class RegisterRequest(
    val email: String,
    val password: String,
    val phone_number: String? = null,
    val first_name: String = "",
    val last_name: String = "",
)

@Serializable data class RefreshRequest(val refresh: String)
@Serializable data class LogoutRequest(val refresh: String)
@Serializable data class TwoFactorVerifyRequest(val challenge: String, val code: String)
@Serializable data class TwoFactorCodeRequest(val code: String)
@Serializable data class TwoFactorDisableRequest(val password: String, val code: String)
@Serializable data class PasswordResetRequest(val email: String)
@Serializable data class PasswordResetConfirmRequest(val uid: String, val token: String, val password: String)
@Serializable data class CreateConversationRequest(val listing: Int)
@Serializable data class SendMessageRequest(val conversation: Int, val body: String)
@Serializable data class CreateOrderRequest(val listing: Int)
@Serializable data class DisputeRequest(val reason: String)
@Serializable data class InitializePaymentRequest(val order_id: Int)

@Serializable data class ProfileUpdate(val bio: String, val location: String, val theme_preference: String)

@Serializable
data class UpdateProfileRequest(
    val first_name: String,
    val last_name: String,
    val phone_number: String?,
    val profile: ProfileUpdate,
)

@Serializable data class CreateCommentRequest(val listing: Int, val body: String, val parent: Int? = null)
@Serializable data class CreateLikeRequest(val listing: Int)
@Serializable data class CreateFollowRequest(val target_type: String, val target_id: Int)

@Serializable
data class CreateMerchantApplicationRequest(
    val business_name: String,
    val business_description: String,
    val business_phone: String,
    val business_address: String,
)

@Serializable data class CreateReviewRequest(val order: Int, val rating: Int, val comment: String)
@Serializable data class CreateReportRequest(val target_type: String, val target_id: Int, val reason: String)

@Serializable data class PayoutAccountRequest(val bank_code: String, val account_number: String)

interface ChoropiaApi {
    @GET("payouts/banks/")
    suspend fun listBanks(): List<Bank>

    @GET("payouts/account/")
    suspend fun getPayoutAccount(): PayoutAccount

    @PUT("payouts/account/")
    suspend fun savePayoutAccount(@Body body: PayoutAccountRequest): PayoutAccount

    @DELETE("payouts/account/")
    suspend fun deletePayoutAccount()

    // --- auth ---------------------------------------------------------------------------------
    @POST("auth/login/")
    suspend fun login(@Body body: LoginRequest): LoginResponse

    @POST("auth/2fa/verify/")
    suspend fun verifyTwoFactor(@Body body: TwoFactorVerifyRequest): AuthResponse

    @GET("auth/2fa/status/")
    suspend fun twoFactorStatus(): TwoFactorStatus

    @POST("auth/2fa/setup/")
    suspend fun twoFactorSetup(): TwoFactorSetup

    @POST("auth/2fa/confirm/")
    suspend fun twoFactorConfirm(@Body body: TwoFactorCodeRequest): TwoFactorConfirmed

    @POST("auth/2fa/disable/")
    suspend fun twoFactorDisable(@Body body: TwoFactorDisableRequest)

    @POST("auth/register/")
    suspend fun register(@Body body: RegisterRequest): AuthResponse

    @POST("auth/refresh/")
    suspend fun refresh(@Body body: RefreshRequest): RefreshResponse

    @POST("auth/logout/")
    suspend fun logout(@Body body: LogoutRequest)

    @POST("auth/password-reset/")
    suspend fun requestPasswordReset(@Body body: PasswordResetRequest)

    @POST("auth/password-reset/confirm/")
    suspend fun confirmPasswordReset(@Body body: PasswordResetConfirmRequest)

    @GET("users/me/")
    suspend fun me(): User

    @PATCH("users/me/")
    suspend fun updateProfile(@Body body: UpdateProfileRequest): User

    // --- listings & feed ----------------------------------------------------------------------
    @GET("listings/")
    suspend fun listListings(
        @Query("category") categorySlug: String? = null,
        @Query("search") search: String? = null,
        @Query("ordering") ordering: String? = null,
        @Query("condition") condition: String? = null,
        @Query("min_price") minPrice: String? = null,
        @Query("max_price") maxPrice: String? = null,
        @Query("merchant") merchantId: Int? = null,
        @Query("mine") mine: Boolean? = null,
    ): PaginatedResponse<Listing>

    @GET
    suspend fun listingsPage(@Url url: String): PaginatedResponse<Listing>

    @GET("feed/")
    suspend fun feed(): PaginatedResponse<Listing>

    @GET("listings/{id}/")
    suspend fun getListing(@Path("id") id: Int): Listing

    @GET("categories/")
    suspend fun listCategories(): List<Category>

    @Multipart
    @POST("listings/")
    suspend fun createListing(
        @PartMap fields: Map<String, @JvmSuppressWildcards RequestBody>,
        @Part photos: List<MultipartBody.Part>,
    ): Listing

    @POST("listings/{id}/mark_sold/")
    suspend fun markSold(@Path("id") id: Int): Listing

    // --- social -------------------------------------------------------------------------------
    @GET("comments/")
    suspend fun listComments(@Query("listing") listingId: Int): PaginatedResponse<Comment>

    @POST("comments/")
    suspend fun createComment(@Body body: CreateCommentRequest): Comment

    @GET("likes/")
    suspend fun listMyLikes(): PaginatedResponse<Like>

    @GET
    suspend fun likesPage(@Url url: String): PaginatedResponse<Like>

    @POST("likes/")
    suspend fun likeListing(@Body body: CreateLikeRequest): Like

    @DELETE("likes/{id}/")
    suspend fun unlikeListing(@Path("id") id: Int)

    @GET("follows/")
    suspend fun listMyFollows(): PaginatedResponse<Follow>

    @GET
    suspend fun followsPage(@Url url: String): PaginatedResponse<Follow>

    @POST("follows/")
    suspend fun follow(@Body body: CreateFollowRequest): Follow

    @DELETE("follows/{id}/")
    suspend fun unfollow(@Path("id") id: Int)

    // --- chat ---------------------------------------------------------------------------------
    @GET("conversations/")
    suspend fun listConversations(): PaginatedResponse<Conversation>

    @GET("conversations/{id}/")
    suspend fun getConversation(@Path("id") id: Int): Conversation

    @POST("conversations/")
    suspend fun startConversation(@Body body: CreateConversationRequest): Conversation

    @GET("messages/")
    suspend fun getMessages(@Query("conversation") conversationId: Int): PaginatedResponse<Message>

    @GET
    suspend fun messagesPage(@Url url: String): PaginatedResponse<Message>

    @POST("messages/")
    suspend fun sendMessage(@Body body: SendMessageRequest): Message

    @Multipart
    @POST("messages/")
    suspend fun sendAttachment(
        @Part("conversation") conversation: RequestBody,
        @Part("body") body: RequestBody,
        @Part("duration_seconds") durationSeconds: RequestBody?,
        @Part attachment: MultipartBody.Part,
    ): Message

    // --- orders & payments --------------------------------------------------------------------
    @GET("orders/")
    suspend fun listOrders(): PaginatedResponse<Order>

    @GET("orders/{id}/")
    suspend fun getOrder(@Path("id") id: Int): Order

    @POST("orders/")
    suspend fun createOrder(@Body body: CreateOrderRequest): Order

    @POST("orders/{id}/confirm_receipt/")
    suspend fun confirmReceipt(@Path("id") id: Int): Order

    @POST("orders/{id}/open_dispute/")
    suspend fun openDispute(@Path("id") id: Int, @Body body: DisputeRequest): Order

    @POST("orders/{id}/mark_in_transit/")
    suspend fun markInTransit(@Path("id") id: Int): Order

    @POST("orders/{id}/mark_delivered/")
    suspend fun markDelivered(@Path("id") id: Int): Order

    @GET("payouts/preview/")
    suspend fun commissionPreview(@Query("price") price: String): CommissionPreview

    @POST("orders/{id}/assign_courier/")
    suspend fun assignCourier(@Path("id") id: Int): Order

    @POST("payments/initialize/")
    suspend fun initializePayment(@Body body: InitializePaymentRequest): PaymentInitResponse

    @POST("payments/verify/")
    suspend fun verifyPayment(@Body body: InitializePaymentRequest): PaymentVerifyResponse

    // --- merchants ----------------------------------------------------------------------------
    @GET("merchants/{id}/")
    suspend fun getMerchant(@Path("id") id: Int): Merchant

    @POST("merchant-applications/")
    suspend fun applyForMerchant(@Body body: CreateMerchantApplicationRequest): MerchantApplication

    // --- notifications / reviews / moderation -------------------------------------------------
    @GET("notifications/")
    suspend fun listNotifications(): PaginatedResponse<AppNotification>

    @POST("notifications/{id}/mark_read/")
    suspend fun markNotificationRead(@Path("id") id: Int)

    @POST("notifications/mark-all-read/")
    suspend fun markAllNotificationsRead()

    @GET("reviews/")
    suspend fun listReviewsFor(@Query("user") userId: Int): PaginatedResponse<Review>

    @POST("reviews/")
    suspend fun createReview(@Body body: CreateReviewRequest): Review

    @POST("reports/")
    suspend fun report(@Body body: CreateReportRequest): Report
}
