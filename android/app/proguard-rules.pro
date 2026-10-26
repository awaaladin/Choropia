# kotlinx.serialization: keep generated serializers for our @Serializable DTOs.
-keepattributes *Annotation*, InnerClasses, Signature, Exceptions
-dontnote kotlinx.serialization.AnnotationsKt
-keepclassmembers class kotlinx.serialization.json.** { *** Companion; }
-keepclasseswithmembers class kotlinx.serialization.json.** { kotlinx.serialization.KSerializer serializer(...); }
-keep,includedescriptorclasses class com.choropia.app.**$$serializer { *; }
-keepclassmembers class com.choropia.app.** { *** Companion; }
-keepclasseswithmembers class com.choropia.app.** { kotlinx.serialization.KSerializer serializer(...); }

# Retrofit interface + suspend functions (R8 full mode).
-keep,allowobfuscation,allowshrinking interface retrofit2.Call
-keep,allowobfuscation,allowshrinking class kotlin.coroutines.Continuation
-keep interface com.choropia.app.data.network.ChoropiaApi { *; }
-dontwarn retrofit2.KotlinExtensions
-dontwarn retrofit2.KotlinExtensions$*

-dontwarn okhttp3.internal.platform.**
-dontwarn org.conscrypt.**
-dontwarn org.bouncycastle.**
-dontwarn org.openjsse.**
