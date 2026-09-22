package com.choropia.app.data.model

import kotlinx.serialization.Serializable

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
    val email: String,
    val phone_number: String? = null,
    val first_name: String = "",
    val last_name: String = "",
    val profile: Profile? = null,
)

@Serializable
data class AuthResponse(
    val access: String,
    val refresh: String,
    val user: User,
)

@Serializable
data class RefreshResponse(val access: String)

@Serializable
data class ListingPhoto(val id: Int, val image: String, val order: Int = 0)

@Serializable
data class Category(val id: Int, val name: String, val slug: String, val parent: Int? = null)

@Serializable
data class Listing(
    val id: Int,
    val title: String,
    val description: String = "",
    val price: String,
    val condition: String,
    val status: String,
    val location: String = "",
    val category: Int,
    val owner_id: Int? = null,
    val merchant: Int? = null,
    val views_count: Int = 0,
    val likes_count: Int = 0,
    val comments_count: Int = 0,
    val is_liked: Boolean = false,
    val photos: List<ListingPhoto> = emptyList(),
    val cover_photo: String? = null,
    val created_at: String? = null,
)

@Serializable
data class PaginatedResponse<T>(
    val count: Int = 0,
    val next: String? = null,
    val previous: String? = null,
    val results: List<T> = emptyList(),
)

@Serializable
data class Conversation(
    val id: Int,
    val listing: Int,
    val buyer: Int? = null,
    val seller: Int? = null,
    val order: Int? = null,
    val last_message: Message? = null,
)

@Serializable
data class Message(
    val id: Int? = null,
    val conversation: Int,
    val sender_id: Int? = null,
    val body: String,
    val read_at: String? = null,
    val created_at: String? = null,
)

@Serializable
data class OrderStatusHistoryEntry(
    val from_status: String,
    val to_status: String,
    val note: String = "",
    val created_at: String,
)

@Serializable
data class Order(
    val id: Int,
    val listing: Int,
    val buyer: Int,
    val seller: Int,
    val price: String,
    val status: String,
    val dispute_reason: String = "",
    val history: List<OrderStatusHistoryEntry> = emptyList(),
    val created_at: String? = null,
)

@Serializable
data class Merchant(
    val id: Int,
    val owner_id: Int,
    val business_name: String,
    val description: String = "",
    val logo: String? = null,
    val location: String = "",
    val status: String,
    val followers_count: Int = 0,
    val created_at: String? = null,
)

@Serializable
data class Notification(
    val id: Int,
    val notification_type: String,
    val verb: String,
    val actor: Int? = null,
    val is_read: Boolean,
    val created_at: String,
)

@Serializable
data class PaymentInitResponse(
    val reference: String,
    val authorization_url: String,
    val amount: String,
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
data class Like(
    val id: Int,
    val listing: Int,
    val created_at: String? = null,
)

@Serializable
data class Follow(
    val id: Int,
    val object_id: Int,
    val target_type_display: String,
    val created_at: String? = null,
)

@Serializable
data class MerchantApplication(
    val id: Int,
    val business_name: String,
    val business_description: String = "",
    val business_phone: String,
    val business_address: String,
    val status: String,
    val rejection_reason: String = "",
    val created_at: String? = null,
)

@Serializable
data class Report(
    val id: Int,
    val status: String,
    val created_at: String? = null,
)

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
