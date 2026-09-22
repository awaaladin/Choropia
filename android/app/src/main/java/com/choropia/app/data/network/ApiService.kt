package com.choropia.app.data.network

import com.choropia.app.data.model.AuthResponse
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
import com.choropia.app.data.model.PaginatedResponse
import com.choropia.app.data.model.PaymentInitResponse
import com.choropia.app.data.model.RefreshResponse
import com.choropia.app.data.model.Report
import com.choropia.app.data.model.Review
import com.choropia.app.data.model.User
import kotlinx.serialization.Serializable
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

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
@Serializable data class CreateConversationRequest(val listing: Int)
@Serializable data class SendMessageRequest(val conversation: Int, val body: String)
@Serializable data class CreateOrderRequest(val listing: Int)
@Serializable data class DisputeRequest(val reason: String)
@Serializable data class InitializePaymentRequest(val order_id: Int)

@Serializable
data class CreateListingRequest(
    val title: String,
    val description: String,
    val price: String,
    val condition: String,
    val category: Int,
    val location: String = "",
)

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

interface ChoropiaApi {
    @POST("auth/login/")
    suspend fun login(@Body body: LoginRequest): AuthResponse

    @POST("auth/register/")
    suspend fun register(@Body body: RegisterRequest): AuthResponse

    @POST("auth/refresh/")
    suspend fun refresh(@Body body: RefreshRequest): RefreshResponse

    @POST("auth/logout/")
    suspend fun logout(@Body body: LogoutRequest)

    @GET("users/me/")
    suspend fun me(): User

    @GET("listings/")
    suspend fun listListings(@Query("category") category: String? = null): PaginatedResponse<Listing>

    @GET("feed/")
    suspend fun feed(): PaginatedResponse<Listing>

    @GET("listings/{id}/")
    suspend fun getListing(@Path("id") id: Int): Listing

    @GET("conversations/")
    suspend fun listConversations(): PaginatedResponse<Conversation>

    @POST("conversations/")
    suspend fun startConversation(@Body body: CreateConversationRequest): Conversation

    @GET("messages/")
    suspend fun getMessages(@Query("conversation") conversationId: Int): PaginatedResponse<Message>

    @POST("messages/")
    suspend fun sendMessage(@Body body: SendMessageRequest): Message

    @GET("orders/")
    suspend fun listOrders(): PaginatedResponse<Order>

    @POST("orders/")
    suspend fun createOrder(@Body body: CreateOrderRequest): Order

    @POST("orders/{id}/confirm_receipt/")
    suspend fun confirmReceipt(@Path("id") id: Int): Order

    @POST("orders/{id}/open_dispute/")
    suspend fun openDispute(@Path("id") id: Int, @Body body: DisputeRequest): Order

    @POST("orders/{id}/assign_courier/")
    suspend fun assignCourier(@Path("id") id: Int): Order

    @GET("orders/{id}/")
    suspend fun getOrder(@Path("id") id: Int): Order

    @POST("payments/initialize/")
    suspend fun initializePayment(@Body body: InitializePaymentRequest): PaymentInitResponse

    @GET("categories/")
    suspend fun listCategories(): List<Category>

    @POST("listings/")
    suspend fun createListing(@Body body: CreateListingRequest): Listing

    @GET("merchants/{id}/")
    suspend fun getMerchant(@Path("id") id: Int): Merchant

    @GET("listings/")
    suspend fun listMerchantListings(@Query("merchant") merchantId: Int): PaginatedResponse<Listing>

    @GET("notifications/")
    suspend fun listNotifications(): PaginatedResponse<Notification>

    @POST("notifications/{id}/mark_read/")
    suspend fun markNotificationRead(@Path("id") id: Int): Notification

    @POST("notifications/mark-all-read/")
    suspend fun markAllNotificationsRead()

    @PATCH("users/me/")
    suspend fun updateProfile(@Body body: UpdateProfileRequest): User

    @GET("comments/")
    suspend fun listComments(@Query("listing") listingId: Int): PaginatedResponse<Comment>

    @POST("comments/")
    suspend fun createComment(@Body body: CreateCommentRequest): Comment

    @GET("likes/")
    suspend fun listMyLikes(): PaginatedResponse<Like>

    @POST("likes/")
    suspend fun likeListing(@Body body: CreateLikeRequest): Like

    @DELETE("likes/{id}/")
    suspend fun unlikeListing(@Path("id") id: Int)

    @GET("follows/")
    suspend fun listMyFollows(): PaginatedResponse<Follow>

    @POST("follows/")
    suspend fun follow(@Body body: CreateFollowRequest): Follow

    @DELETE("follows/{id}/")
    suspend fun unfollow(@Path("id") id: Int)

    @POST("merchant-applications/")
    suspend fun applyForMerchant(@Body body: CreateMerchantApplicationRequest): MerchantApplication

    @GET("reviews/")
    suspend fun listReviewsFor(@Query("user") userId: Int): PaginatedResponse<Review>

    @POST("reviews/")
    suspend fun createReview(@Body body: CreateReviewRequest): Review

    @POST("reports/")
    suspend fun reportListing(@Body body: CreateReportRequest): Report
}
