package com.nutriscan.app.data.remote

import com.google.gson.Gson
import retrofit2.Response

/** Turns an HTTP status code into copy a user can actually act on. */
fun friendlyErrorMessage(code: Int): String = when (code) {
    400 -> "Please check your details and try again."
    401 -> "Your session expired. Please log in again."
    402 -> "That subscription isn't active."
    409 -> "This purchase is already linked to another account."
    502, 503 -> "Subscriptions aren't available right now. Please try again shortly."
    403 -> "You don't have access to do that."
    404 -> "We couldn't find that."
    in 500..599 -> "Something went wrong on our end. Please try again shortly."
    else -> "Something went wrong. Please try again."
}

/** The structured error body the server sends for photo identification:
 * a user-facing [detail], a stable [reason] code, and whether better photos
 * ([retake]) could fix it. */
data class ServerError(
    val detail: String? = null,
    val reason: String? = null,
    val retake: Boolean = false,
    // A fixed safety message (e.g. call 112) the server attaches even when the AI is down.
    val notice: String? = null,
)

fun parseServerError(response: Response<*>): ServerError? = try {
    response.errorBody()?.string()?.let { Gson().fromJson(it, ServerError::class.java) }
} catch (_: Exception) {
    null // body wasn't JSON (e.g. a gateway error page)
}

/** An error message that says what happened. Pass the already-parsed [error]
 * when the caller has read the body (it can only be read once); otherwise it is
 * parsed here. Falls back to the HTTP status for cases where the server gave no
 * explanation of its own. */
fun describeFailure(code: Int, error: ServerError?): String {
    error?.detail?.takeIf { it.isNotBlank() }?.let { return it }
    return when (code) {
        504 -> "The server took too long to respond (timeout, HTTP 504). Please try again."
        502, 503 -> "The server is temporarily unavailable (HTTP $code). Please try again shortly."
        in 500..599 -> "The server hit an error (HTTP $code). Please try again shortly."
        else -> "${friendlyErrorMessage(code)} (HTTP $code)"
    }
}

fun describeFailure(response: Response<*>): String = describeFailure(response.code(), parseServerError(response))
