import java.net.URI

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("org.jetbrains.kotlin.kapt")
    id("com.google.dagger.hilt.android")
}

val productionApiUrl = "https://api.yudyai.xyz/"
val releaseApiUrl = providers.gradleProperty("YUDY_RELEASE_API_URL").getOrElse(productionApiUrl)
val signingValues = listOf("YUDY_KEYSTORE_PATH", "YUDY_KEYSTORE_PASSWORD", "YUDY_KEY_ALIAS", "YUDY_KEY_PASSWORD")
    .map { providers.environmentVariable(it).orNull }
require(signingValues.all { it == null } || signingValues.all { !it.isNullOrBlank() }) {
    "Set all four YUDY signing environment variables, or leave all unset for an unsigned build"
}

android {
    namespace = "app.yudy"
    compileSdk = 36
    defaultConfig {
        applicationId = "app.yudy"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }
    signingConfigs {
        if (signingValues.all { it != null }) create("release") {
            storeFile = file(signingValues[0]!!)
            storePassword = signingValues[1]
            keyAlias = signingValues[2]
            keyPassword = signingValues[3]
        }
    }
    buildTypes {
        debug {
            val apiUrl = providers.gradleProperty("YUDY_API_URL")
                .getOrElse(productionApiUrl)
            require(apiUrl.startsWith("http://") || apiUrl.startsWith("https://"))
            require(apiUrl.endsWith("/")) { "YUDY_API_URL must end with /" }
            buildConfigField("String", "API_BASE_URL", "\"${apiUrl.replace("\\", "\\\\").replace("\"", "\\\"")}\"")
        }
        release {
            buildConfigField("String", "API_BASE_URL", "\"${releaseApiUrl.replace("\\", "\\\\").replace("\"", "\\\"")}\"")
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = signingConfigs.findByName("release")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
}
tasks.matching { it.name == "preReleaseBuild" }.configureEach {
    doFirst {
        val uri = runCatching { URI(releaseApiUrl) }.getOrNull()
        require(uri != null && uri.scheme == "https" && !uri.host.isNullOrBlank()
            && uri.userInfo == null && uri.query == null && uri.fragment == null
            && releaseApiUrl.endsWith("/")) {
            "YUDY_RELEASE_API_URL must be an HTTPS base URL ending in /, without credentials, query or fragment"
        }
    }
}
kotlin { jvmToolchain(17) }

kapt { arguments { arg("room.schemaLocation", "$projectDir/schemas") } }

dependencies {
    implementation("androidx.room:room-runtime:2.8.4")
    implementation("androidx.room:room-ktx:2.8.4")
    kapt("androidx.room:room-compiler:2.8.4")
    implementation("com.google.dagger:hilt-android:2.57.1")
    kapt("com.google.dagger:hilt-compiler:2.57.1")
    implementation("androidx.navigation:navigation-compose:2.9.2")
    implementation("androidx.datastore:datastore-preferences:1.1.7")
    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-moshi:2.11.0")
    implementation("com.squareup.moshi:moshi-kotlin:1.15.2")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("io.coil-kt:coil-compose:2.7.0")
    testImplementation("com.squareup.okhttp3:mockwebserver:4.12.0")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.10.2")
    implementation(platform("androidx.compose:compose-bom:2025.08.00"))
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.9.2")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.9.2")
    debugImplementation("androidx.compose.ui:ui-tooling")
    testImplementation("junit:junit:4.13.2")
    androidTestImplementation(platform("androidx.compose:compose-bom:2025.08.00"))
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test:runner:1.6.2")
    androidTestImplementation("androidx.test.uiautomator:uiautomator:2.3.0")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}
