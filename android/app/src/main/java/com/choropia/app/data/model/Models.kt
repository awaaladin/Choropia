package com.choropia.app.data.model

import kotlinx.serialization.Serializable

// DTOs mirror the Django serializers one-to-one (accounts, listings, social, chat, orders,
// notifications, merchants, reviews). Every field is defaulted so a backend that adds, removes or
// nulls a field never crashes decoding — `ignoreUnknownKeys` handles the extras.

@Serializable
data class Profile(
    val bio: String = "",
    val avatar: String? = null,
    val location: String = "",
    val theme_preference: String = "light",
)

@Serializable
data class User(
    val id: Int,
    val email: String = "",
    val phone_number: String? = null,
    val first_name: String = "",
    val last_name: String = "",
    val date_joined: String? = null,
    val profile: Profile? = null,
    val two_factor_enabled: Boolean = false,
) {
    val displayName: String
        get() = listOf(first_name, last_name).filter { it.isNotBlank() }.joinToString(" ")
            .ifBlank { email.substringBefore('@').ifBlank { "Choropia member" } }
}

@Serializable
data class AuthResponse(val access: String, val refresh: String, val user: User)

/** Login answer: tokens, or a second-factor challenge when the account has 2-step verification on. */
@Serializable
data class LoginResponse(
    val access: String? = null,
    val refresh: String? = null,
    val user: User? = null,
    val two_factor_required: Boolean = false,
    val challenge: String? = null,
)

@Serializable
data class TwoFactorStatus(val enabled: Boolean = false, val recovery_codes_remaining: Int = 0)

@Serializable
data class TwoFactorSetup(val secret: String, val otpauth_uri: String)

@Serializable
data class TwoFactorConfirmed(val enabled: Boolean = true, val recovery_codes: List<String> = emptyList())

@Serializable
data class RefreshResponse(val access: String, val refresh: String? = null)

@Serializable
data class ListingPhoto(val id: Int, val image: String, val order: Int = 0)

@Serializable
data class Category(val id: Int, val name: String, val slug: String, val parent: Int? = null)

@Serializable
data class Listing(
    val id: Int,
    val title: String,
    val description: String = "",
    val price: String = "0",
    val condition: String = "used",
    val status: String = "active",
    val location: String = "",
    val category: Int = 0,
    // Detail payload
    val owner_id: Int? = null,
    val merchant: Int? = null,
    // List payload
    val merchant_id: Int? = null,
    val seller_id: Int? = null,
    val seller_name: String = "",
    val seller_avatar: String? = null,
    val views_count: Int = 0,
    val likes_count: Int = 0,
    val comments_count: Int = 0,
    val is_liked: Boolean = false,
    val photos: List<ListingPhoto> = emptyList(),
    val cover_photo: String? = null,
    val created_at: String? = null,
) {
    /** The merchant storefront this listing was posted under, if any (list vs detail payloads differ). */
    val merchantRef: Int? get() = merchant_id ?: merchant

    /** The account a buyer is dealing with — owner for detail payloads, seller_id for list payloads. */
    val sellerUserId: Int? get() = owner_id ?: if (merchantRef == null) seller_id else null

    val imageUrls: List<String>
        get() = photos.sortedBy { it.order }.map { it.image }.ifEmpty { listOfNotNull(cover_photo) }
}

@Serializable
data class PaginatedResponse<T>(
    val count: Int = 0,
    val next: String? = null,
    val previous: String? = null,
    val results: List<T> = emptyList(),
)

@Serializable
data class Message(
    val id: Int? = null,
    val conversation: Int,
    val sender_id: Int? = null,
    val body: String = "",
    val attachment: String? = null,
    val attachment_type: String = "",
    val duration_seconds: Int? = null,
    val read_at: String? = null,
    val created_at: String? = null,
)

@Serializable
data class Conversation(
    val id: Int,
    val listing: Int,
    val listing_title: String = "",
    val buyer: Int? = null,
    val seller: Int? = null,
    val other_party_name: String? = null,
    val other_party_avatar: String? = null,
    val order: Int? = null,
    val last_message: Message? = null,
    val created_at: String? = null,
    val updated_at: String? = null,
)

@Serializable
data class OrderStatusHistoryEntry(
    val from_status: String = "",
    val to_status: String,
    val actor: Int? = null,
    val note: String = "",
    val created_at: String = "",
)

@Serializable
data class Order(
    val id: Int,
    val listing: Int,
    val listing_title: String = "",
    val listing_cover_photo: String? = null,
    val buyer: Int,
    val buyer_name: String = "",
    val seller: Int,
    val seller_name: String = "",
    val price: String = "0",
    val status: String,
    val delivered_at: String? = null,
    val confirmed_at: String? = null,
    val completed_at: String? = null,
    val dispute_reason: String = "",
    val history: List<OrderStatusHistoryEntry> = emptyList(),
    val payout: OrderPayout? = null,   // only present for the seller
    val created_at: String? = null,
)

/** What the seller will be / was paid for an order, after Choropia's commission. */
@Serializable
data class OrderPayout(
    val status: String = "",
    val status_label: String = "",
    val gross_amount: String = "0",
    val commission_amount: String = "0",
    val commission_rate: String = "0",
    val net_amount: String = "0",
    val bank_name: String = "",
    val account_last4: String = "",
)

@Serializable
data class Bank(val code: String, val name: String)

/** What a seller pays and receives for a price (computed by the server, which owns the rates). */
@Serializable
data class CommissionPreview(
    val price: String = "0",
    val commission_percent: String = "0",
    val commission_amount: String = "0",
    val you_receive: String = "0",
)

/** The seller's payout bank account. The full number is never sent to the app. */
@Serializable
data class PayoutAccount(
    val configured: Boolean = false,
    val bank_code: String = "",
    val bank_name: String = "",
    val account_last4: String = "",
    val account_name: String = "",
)

@Serializable
data class Merchant(
    val id: Int,
    val owner_id: Int = 0,
    val business_name: String,
    val description: String = "",
    val logo: String? = null,
    val location: String = "",
    val status: String = "",
    val followers_count: Int = 0,
    val created_at: String? = null,
)

@Serializable
data class AppNotification(
    val id: Int,
    val notification_type: String = "",
    val verb: String = "",
    val actor: Int? = null,
    val target_type: String? = null,
    val target_object_id: Int? = null,
    val is_read: Boolean = false,
    val created_at: String = "",
)

@Serializable
data class PaymentInitResponse(
    val reference: String = "",
    val authorization_url: String,
    val amount: String = "",
    val crypto_amount: String? = null,
    val crypto_currency: String? = null,
)

@Serializable
data class PaymentVerifyResponse(
    val reference: String = "",
    val status: String = "",
    val order_status: String = "",
)

@Serializable
data class Comment(
    val id: Int,
    val listing: Int,
    val author_id: Int? = null,
    val parent: Int? = null,
    val body: String,
    val created_at: String? = null,
)

@Serializable
data class Like(val id: Int, val listing: Int, val created_at: String? = null)

@Serializable
data class Follow(
    val id: Int,
    val object_id: Int,
    val target_type_display: String = "",
    val created_at: String? = null,
)

@Serializable
data class MerchantApplication(
    val id: Int,
    val business_name: String,
    val business_description: String = "",
    val business_phone: String = "",
    val business_address: String = "",
    val status: String = "pending",
    val rejection_reason: String = "",
    val created_at: String? = null,
)

@Serializable
data class Report(val id: Int, val status: String = "", val created_at: String? = null)

@Serializable
data class Review(
    val id: Int,
    val order: Int,
    val reviewer: Int? = null,
    val reviewee: Int? = null,
    val rating: Int,
    val comment: String = "",
    val created_at: String? = null,
)
