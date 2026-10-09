package app.yudy.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.Shapes
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.unit.dp

object YudyColors {
    val Midnight = Color(0xFF0D1514)
    val Surface = Color(0xFF101817)
    val SurfaceVariant = Color(0xFF182526)
    val Cyan = Color(0xFF0BB7C3)
    val CyanDeep = Color(0xFF177B86)
    val Mint = Color(0xFFC6DEE4)
    val White = Color(0xFFE6EAEA)
    val Muted = Color(0xFF99A6AB)
    val Line = Color(0xFF2B3334)
    val LightCanvas = Color(0xFFBAD1D7)
}

private val SeekerSans = FontFamily.SansSerif
private val SeekerMono = FontFamily.Monospace

private val DefaultTypography = Typography()
private val YudyTypography = with(DefaultTypography) {
    Typography(
        displayLarge = displayLarge.copy(fontFamily = SeekerSans, fontWeight = FontWeight.Normal),
        displayMedium = displayMedium.copy(fontFamily = SeekerSans, fontWeight = FontWeight.Normal),
        displaySmall = displaySmall.copy(fontFamily = SeekerSans, fontWeight = FontWeight.Normal,
            fontSize = 40.sp, lineHeight = 44.sp, letterSpacing = (-1.2).sp),
        headlineLarge = headlineLarge.copy(fontFamily = SeekerSans, fontWeight = FontWeight.Medium,
            letterSpacing = (-0.7).sp),
        headlineMedium = headlineMedium.copy(fontFamily = SeekerSans, fontWeight = FontWeight.Medium,
            letterSpacing = (-0.5).sp),
        headlineSmall = headlineSmall.copy(fontFamily = SeekerSans, fontWeight = FontWeight.Medium,
            letterSpacing = (-0.3).sp),
        titleLarge = titleLarge.copy(fontFamily = SeekerSans, fontWeight = FontWeight.Medium),
        titleMedium = titleMedium.copy(fontFamily = SeekerSans, fontWeight = FontWeight.Medium),
        titleSmall = titleSmall.copy(fontFamily = SeekerSans, fontWeight = FontWeight.Medium),
        bodyLarge = bodyLarge.copy(fontFamily = SeekerSans),
        bodyMedium = bodyMedium.copy(fontFamily = SeekerSans),
        bodySmall = bodySmall.copy(fontFamily = SeekerSans),
        labelLarge = labelLarge.copy(fontFamily = SeekerSans, fontWeight = FontWeight.Medium),
        labelMedium = labelMedium.copy(fontFamily = SeekerSans, fontWeight = FontWeight.Medium),
        labelSmall = labelSmall.copy(fontFamily = SeekerMono, fontWeight = FontWeight.Normal),
    )
}

private val YudyColorScheme = darkColorScheme(
    primary = YudyColors.White,
    onPrimary = YudyColors.Midnight,
    primaryContainer = Color(0xFF2D3F41),
    onPrimaryContainer = YudyColors.Mint,
    secondary = YudyColors.Cyan,
    onSecondary = YudyColors.Midnight,
    secondaryContainer = Color(0xFF264F53),
    onSecondaryContainer = YudyColors.Mint,
    tertiary = YudyColors.Mint,
    onTertiary = YudyColors.Midnight,
    tertiaryContainer = Color(0xFF2D4F52),
    onTertiaryContainer = YudyColors.Mint,
    background = YudyColors.Midnight,
    onBackground = YudyColors.White,
    surface = YudyColors.Surface,
    onSurface = YudyColors.White,
    surfaceVariant = YudyColors.SurfaceVariant,
    onSurfaceVariant = YudyColors.Muted,
    outline = Color(0xFF596465),
    outlineVariant = YudyColors.Line,
    surfaceContainer = YudyColors.Surface,
    surfaceContainerHigh = YudyColors.SurfaceVariant,
    error = Color(0xFFFF8E92),
    errorContainer = Color(0xFF4E2024),
    onErrorContainer = Color(0xFFFFDADB),
)

private val YudyShapes = Shapes(
    extraSmall = RoundedCornerShape(6.dp),
    small = RoundedCornerShape(10.dp),
    medium = RoundedCornerShape(12.dp),
    large = RoundedCornerShape(16.dp),
    extraLarge = RoundedCornerShape(22.dp),
)

@Composable
fun YudyTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = YudyColorScheme, typography = YudyTypography,
        shapes = YudyShapes, content = content)
}
