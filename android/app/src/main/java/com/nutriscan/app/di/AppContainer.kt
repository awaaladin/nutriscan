package com.nutriscan.app.di

import android.content.Context
import com.nutriscan.app.data.local.AppDatabase
import com.nutriscan.app.data.local.SessionManager
import com.nutriscan.app.data.remote.RetrofitClient
import com.nutriscan.app.data.repository.NutriScanRepository

/** Minimal manual DI container. Deliberately avoids a DI framework for this
 * MVP's surface area; swap for Hilt if the dependency graph grows. */
object AppContainer {
    @Volatile private var repository: NutriScanRepository? = null

    fun repository(context: Context): NutriScanRepository =
        repository ?: synchronized(this) {
            repository ?: build(context).also { repository = it }
        }

    private fun build(context: Context): NutriScanRepository {
        val appContext = context.applicationContext
        val sessionManager = SessionManager(appContext)
        val api = RetrofitClient.create(sessionManager)
        val db = AppDatabase.getInstance(appContext)
        return NutriScanRepository(api, db.cachedScanDao(), sessionManager)
    }
}
