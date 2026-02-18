# ProGuard rules for CHW Clinical Support

# Keep ONNX Runtime classes
-keep class ai.onnxruntime.** { *; }
-keepclassmembers class ai.onnxruntime.** { *; }

# Keep requery SQLite classes
-keep class io.requery.android.database.** { *; }
-keepclassmembers class io.requery.android.database.** { *; }

# Keep data classes
-keep class org.who.chw.clinical.data.** { *; }
-keep class org.who.chw.clinical.brain1.** { *; }
