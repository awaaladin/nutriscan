package com.nutriscan.app.data.remote

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
