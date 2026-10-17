package com.nutriscan.app.ui.util

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.media.ExifInterface
import java.io.File

/**
 * Shrinks a camera photo for upload: scales the longest edge down to [maxEdge]
 * and re-encodes as JPEG. Product photos only need to be legible, and smaller
 * images upload faster on mobile data and cost the AI fewer tokens.
 *
 * CameraX records rotation in EXIF rather than rotating the pixels, and
 * re-encoding drops EXIF, so the rotation is applied to the pixels here --
 * otherwise a portrait shot would reach the AI sideways.
 *
 * Returns [source] itself if it can't be decoded, so a capture is never lost.
 */
fun downscaleForUpload(source: File, maxEdge: Int = 1280, quality: Int = 80): File {
    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    BitmapFactory.decodeFile(source.absolutePath, bounds)
    if (bounds.outWidth <= 0 || bounds.outHeight <= 0) return source

    var sample = 1
    while (maxOf(bounds.outWidth, bounds.outHeight) / (sample * 2) >= maxEdge) sample *= 2
    val decoded = BitmapFactory.decodeFile(
        source.absolutePath,
        BitmapFactory.Options().apply { inSampleSize = sample },
    ) ?: return source

    val rotation = when (
        ExifInterface(source.absolutePath).getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL)
    ) {
        ExifInterface.ORIENTATION_ROTATE_90 -> 90f
        ExifInterface.ORIENTATION_ROTATE_180 -> 180f
        ExifInterface.ORIENTATION_ROTATE_270 -> 270f
        else -> 0f
    }
    val longest = maxOf(decoded.width, decoded.height)
    val scale = if (longest > maxEdge) maxEdge.toFloat() / longest else 1f

    val matrix = Matrix().apply {
        postRotate(rotation)
        postScale(scale, scale)
    }
    val result = Bitmap.createBitmap(decoded, 0, 0, decoded.width, decoded.height, matrix, true)

    val output = File(source.parentFile, "up_${source.name}")
    output.outputStream().use { result.compress(Bitmap.CompressFormat.JPEG, quality, it) }
    if (result !== decoded) decoded.recycle()
    result.recycle()
    source.delete()
    return output
}

/**
 * Copies a photo the user picked from the gallery (a content:// URI) into the cache and
 * shrinks it for upload, with the same EXIF rotation fix as camera photos.
 * Returns null if the file can't be read as an image.
 */
fun importForUpload(context: android.content.Context, uri: android.net.Uri): File? {
    val copy = File(context.cacheDir, "pick_${System.nanoTime()}.jpg")
    return try {
        context.contentResolver.openInputStream(uri)?.use { input ->
            copy.outputStream().use { input.copyTo(it) }
        } ?: return null
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeFile(copy.absolutePath, bounds)
        if (bounds.outWidth <= 0) {
            copy.delete()
            null
        } else {
            downscaleForUpload(copy)
        }
    } catch (_: Exception) {
        copy.delete()
        null
    }
}
