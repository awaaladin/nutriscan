package com.nutriscan.app.data.remote

import com.google.gson.Gson
import com.nutriscan.app.data.local.SessionManager
import kotlinx.coroutines.runBlocking
import okhttp3.Authenticator
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import okhttp3.Route

private data class RefreshRequestBody(val refresh: String)
private data class RefreshResponseBody(val access: String, val refresh: String? = null)

/**
 * Access tokens expire after an hour (see SIMPLE_JWT.ACCESS_TOKEN_LIFETIME);
 * without this every request past that point failed with a bare 401 and the
 * user had to log out and back in manually. Runs on OkHttp's background
 * dispatcher thread, so the blocking refresh call here is safe and is the
 * pattern OkHttp itself documents for 401 recovery.
 */
class TokenAuthenticator(
    private val sessionManager: SessionManager,
    private val baseUrl: String,
) : Authenticator {
    private val gson = Gson()
    private val plainClient = OkHttpClient()

    override fun authenticate(route: Route?, response: Response): Request? {
        if (responseCount(response) >= 2) return null

        val refreshToken = sessionManager.getRefreshTokenBlocking()
        if (refreshToken.isNullOrBlank()) return null

        val requestBody = gson.toJson(RefreshRequestBody(refreshToken))
            .toRequestBody("application/json".toMediaType())
        val refreshRequest = Request.Builder()
            .url(baseUrl.trimEnd('/') + "/api/auth/login/refresh/")
            .post(requestBody)
            .build()

        val refreshed = try {
            plainClient.newCall(refreshRequest).execute().use { refreshResponse ->
                if (!refreshResponse.isSuccessful) return@use null
                refreshResponse.body?.string()
                    ?.let { json -> gson.fromJson(json, RefreshResponseBody::class.java) }
            }
        } catch (_: Exception) {
            null
        }

        if (refreshed == null || refreshed.access.isBlank()) {
            runBlocking { sessionManager.clear() }
            return null
        }

        runBlocking {
            if (refreshed.refresh != null) {
                sessionManager.saveTokens(refreshed.access, refreshed.refresh)
            } else {
                sessionManager.saveAccessToken(refreshed.access)
            }
        }
        return response.request.newBuilder()
            .header("Authorization", "Bearer ${refreshed.access}")
            .build()
    }

    private fun responseCount(response: Response): Int {
        var count = 1
        var prior = response.priorResponse
        while (prior != null) {
            count++
            prior = prior.priorResponse
        }
        return count
    }
}
