package com.choropia.app.data.network

import kotlinx.serialization.SerializationException
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import retrofit2.HttpException
import java.io.IOException

/** A failure the UI can show verbatim. [fieldErrors] lets forms highlight the offending input. */
class ApiException(
    message: String,
    val httpCode: Int? = null,
    val fieldErrors: Map<String, String> = emptyMap(),
) : Exception(message)

private val errorJson = Json { ignoreUnknownKeys = true; isLenient = true }

private val friendlyFieldNames = mapOf(
    "email" to "Email",
    "phone_number" to "Phone number",
    "password" to "Password",
    "first_name" to "First name",
    "last_name" to "Last name",
    "title" to "Title",
    "price" to "Price",
    "category" to "Category",
    "business_name" to "Business name",
    "business_phone" to "Business phone",
    "business_address" to "Business address",
    "reason" to "Reason",
    "body" to "Message",
)

/**
 * Runs an API call and converts every failure mode into an [ApiException] with a human message.
 * Mirrors `extractErrorMessage` in the web frontend's api.js so both clients say the same thing
 * for the same backend error.
 */
suspend fun <T> apiCall(block: suspend () -> T): T = try {
    block()
} catch (e: HttpException) {
    throw e.toApiException()
} catch (e: SerializationException) {
    throw ApiException("Choropia sent a response the app couldn't read. Please update the app.")
} catch (e: IOException) {
    throw ApiException("Can't reach Choropia. Check your connection and try again.")
}

private fun HttpException.toApiException(): ApiException {
    val code = code()
    val raw = runCatching { response()?.errorBody()?.string() }.getOrNull().orEmpty()
    val parsed = runCatching { errorJson.parseToJsonElement(raw) }.getOrNull()
    val fields = mutableMapOf<String, String>()
    val message = parsed?.let { extractMessage(it, fields) }

    val friendly = when {
        code == 429 -> "Too many attempts. Please wait a moment and try again."
        code >= 500 -> "Choropia is having trouble right now. Please try again shortly."
        code == 401 && message == null -> "Please log in again."
        code == 403 && message == null -> "You don't have permission to do that."
        code == 404 && message == null -> "We couldn't find that."
        else -> message
    }
    return ApiException(friendly ?: "Something went wrong (HTTP $code).", code, fields)
}

private fun extractMessage(element: JsonElement, fields: MutableMap<String, String>): String? = when (element) {
    is JsonPrimitive -> element.content.takeIf { it.isNotBlank() }
    is JsonArray -> element.firstNotNullOfOrNull { extractMessage(it, fields) }
    is JsonObject -> {
        val detail = (element["detail"] as? JsonPrimitive)?.content
        if (detail != null) {
            detail
        } else {
            var first: String? = null
            for ((key, value) in element) {
                val text = extractMessage(value, mutableMapOf()) ?: continue
                if (key != "non_field_errors") fields[key] = text
                if (first == null) {
                    first = if (key == "non_field_errors") text else "${friendlyFieldNames[key] ?: key.replace('_', ' ').replaceFirstChar { it.uppercase() }}: $text"
                }
            }
            first
        }
    }
    else -> null
}
