# Gson reflects over these DTOs to (de)serialize API responses; without a
# keep rule R8 renames/strips their fields and parsing silently breaks.
-keep class com.nutriscan.app.data.model.** { *; }
-keep class com.nutriscan.app.data.local.** { *; }

# Retrofit/OkHttp + Gson's own reflection needs (standard recommended rules).
-keepattributes Signature, InnerClasses, EnclosingMethod
-keepattributes RuntimeVisibleAnnotations, RuntimeVisibleParameterAnnotations
-keepattributes AnnotationDefault
-keep class com.google.gson.** { *; }
-keep class * extends com.google.gson.TypeAdapter
-dontwarn okhttp3.**
-dontwarn retrofit2.**
