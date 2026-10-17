package com.nutriscan.app.data.local

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.appPrefsDataStore by preferencesDataStore(name = "nutriscan_app_prefs")

/** App-level (non-health) preferences: display and notification settings,
 * as opposed to SessionManager (auth) or the health profile on the backend. */
class AppPreferencesManager(private val context: Context) {
    private object Keys {
        val DARK_MODE_OVERRIDE_SET = booleanPreferencesKey("dark_mode_override_set")
        val DARK_MODE_ENABLED = booleanPreferencesKey("dark_mode_enabled")
        val NOTIFICATIONS_ENABLED = booleanPreferencesKey("notifications_enabled")
        val AUTO_READ_ALOUD = booleanPreferencesKey("auto_read_aloud")
    }

    /** null = follow system theme. */
    val darkModeOverride: Flow<Boolean?> = context.appPrefsDataStore.data.map { prefs ->
        if (prefs[Keys.DARK_MODE_OVERRIDE_SET] == true) prefs[Keys.DARK_MODE_ENABLED] else null
    }

    val notificationsEnabled: Flow<Boolean> = context.appPrefsDataStore.data.map { prefs ->
        prefs[Keys.NOTIFICATIONS_ENABLED] ?: true
    }

    /** Speak scan results and assistant answers aloud without tapping the speaker button. */
    val autoReadAloud: Flow<Boolean> = context.appPrefsDataStore.data.map { prefs ->
        prefs[Keys.AUTO_READ_ALOUD] ?: false
    }

    suspend fun setAutoReadAloud(enabled: Boolean) {
        context.appPrefsDataStore.edit { prefs -> prefs[Keys.AUTO_READ_ALOUD] = enabled }
    }

    suspend fun setDarkModeOverride(enabled: Boolean?) {
        context.appPrefsDataStore.edit { prefs ->
            if (enabled == null) {
                prefs[Keys.DARK_MODE_OVERRIDE_SET] = false
            } else {
                prefs[Keys.DARK_MODE_OVERRIDE_SET] = true
                prefs[Keys.DARK_MODE_ENABLED] = enabled
            }
        }
    }

    suspend fun setNotificationsEnabled(enabled: Boolean) {
        context.appPrefsDataStore.edit { prefs -> prefs[Keys.NOTIFICATIONS_ENABLED] = enabled }
    }
}
