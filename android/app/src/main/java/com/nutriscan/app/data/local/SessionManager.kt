package com.nutriscan.app.data.local

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.runBlocking

private val Context.dataStore by preferencesDataStore(name = "nutriscan_session")

/** Persists JWT tokens. [getAccessTokenBlocking] is used by the OkHttp
 * auth interceptor, which runs synchronously off the network thread. */
class SessionManager(private val context: Context) {
    private object Keys {
        val ACCESS_TOKEN = stringPreferencesKey("access_token")
        val REFRESH_TOKEN = stringPreferencesKey("refresh_token")
    }

    val accessTokenFlow: Flow<String?> = context.dataStore.data.map { it[Keys.ACCESS_TOKEN] }
    val isLoggedInFlow: Flow<Boolean> = accessTokenFlow.map { !it.isNullOrBlank() }

    suspend fun saveTokens(access: String, refresh: String) {
        context.dataStore.edit { prefs ->
            prefs[Keys.ACCESS_TOKEN] = access
            prefs[Keys.REFRESH_TOKEN] = refresh
        }
    }

    suspend fun clear() {
        context.dataStore.edit { it.clear() }
    }

    fun getAccessTokenBlocking(): String? = runBlocking { accessTokenFlow.first() }
}
