package com.nutriscan.app.data.local

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

@Entity(tableName = "cached_scans")
data class CachedScanEntity(
    @PrimaryKey val barcode: String,
    val productName: String,
    val brand: String?,
    val score: Int,
    val label: String,
    val diabeticRisk: String,
    val explanation: String,
    val scannedAtEpochMs: Long,
)

@Dao
interface CachedScanDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(scan: CachedScanEntity)

    @Query("SELECT * FROM cached_scans ORDER BY scannedAtEpochMs DESC")
    fun observeAll(): Flow<List<CachedScanEntity>>

    @Query("SELECT * FROM cached_scans WHERE barcode = :barcode LIMIT 1")
    suspend fun getByBarcode(barcode: String): CachedScanEntity?
}
