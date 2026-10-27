package com.choropia.app.data.model

import kotlinx.serialization.Serializable

@Serializable
data class Area(val id: Int, val name: String)

@Serializable
data class DriverDocumentStatus(val kind: String, val label: String = "", val uploaded: Boolean = false)

/** The signed-in person's own driver application / profile (null body means they have not applied). */
@Serializable
data class DriverMe(
    val id: Int = 0,
    val status: String = "pending",
    val status_label: String = "",
    val review_note: String = "",
    val full_name: String = "",
    val phone: String = "",
    val whatsapp: String = "",
    val vehicle_type: String = "bike",
    val plate_number: String = "",
    val guarantor_name: String = "",
    val guarantor_phone: String = "",
    val available: Boolean = true,
    val documents: List<DriverDocumentStatus> = emptyList(),
    val documents_complete: Boolean = false,
)

@Serializable
data class RoutePrice(
    val id: Int,
    val from_area: Area,
    val to_area: Area,
    val price: String,
    val is_active: Boolean = true,
    val you_pay: String = "",
)

/** A driver as other people see them: name, vehicle and prices. No contact details. */
@Serializable
data class PublicDriver(
    val id: Int,
    val name: String,
    val vehicle_type: String = "",
    val routes: List<RoutePrice> = emptyList(),
)

/** What a buyer sees while browsing a listing that offers delivery. */
@Serializable
data class ListingDeliveryInfo(
    val enabled: Boolean = false,
    val payer: String = "buyer",
    val pickup_area: Area? = null,
    val drivers: List<PublicDriver> = emptyList(),
)

@Serializable
data class DeliveryDriverInfo(
    val name: String = "",
    val vehicle_type: String = "",
    val plate_number: String = "",
    val phone: String = "",
    val whatsapp: String = "",
)

@Serializable
data class DeliveryContact(val name: String = "", val phone: String = "", val note: String = "")

/** One order's delivery, shaped by the server for whoever is asking (buyer, seller or the assigned driver). */
@Serializable
data class OrderDelivery(
    val id: Int,
    val order: Int,
    val status: String,
    val status_label: String = "",
    val pickup_area: Area,
    val dropoff_area: Area,
    val payer: String = "buyer",
    val fee: String = "0",
    val buyer_share: String = "0",
    val seller_share: String = "0",
    val driver: DeliveryDriverInfo? = null,
    val handover_code: String = "",
    val dropoff_note: String = "",
    val can_cancel_choice: Boolean = false,
    val can_reassign: Boolean = false,
    val drivers_notified: Int = 0,
    val you_earn: String = "",
    val listing_title: String = "",
    val pickup: DeliveryContact? = null,
    val dropoff: DeliveryContact? = null,
    val can_pick_up: Boolean = false,
    val can_deliver: Boolean = false,
)

/** A job alert before acceptance: route and pay only. */
@Serializable
data class JobCard(
    val id: Int,
    val order: Int,
    val listing_title: String = "",
    val pickup_area: Area,
    val dropoff_area: Area,
    val you_earn: String = "0",
    val state: String = "pending",
)

@Serializable
data class DriverJobs(val open: List<JobCard> = emptyList(), val mine: List<OrderDelivery> = emptyList())

@Serializable
data class AddedArea(val id: Int, val name: String)
