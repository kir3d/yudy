package app.yudy.ui.assets

import java.math.BigDecimal
import java.text.DecimalFormat
import java.text.DecimalFormatSymbols
import java.util.Locale

fun amount(value: String?): String {
    val number = value?.toBigDecimalOrNull() ?: return "Unavailable"
    val magnitude = number.abs()
    val units = listOf("1000000000000" to "T", "1000000000" to "B", "1000000" to "M", "1000" to "K")
    val unit = units.firstOrNull { magnitude >= BigDecimal(it.first) }
    val scaled = if (unit == null) number else number.divide(BigDecimal(unit.first))
    return DecimalFormat("#,##0.##", DecimalFormatSymbols(Locale.US)).format(scaled) + (unit?.second ?: "")
}
fun money(value: String?, currency: String): String = if (value == null) "Price unavailable"
    else (if (currency == "USD") "$" else "$currency ") + DecimalFormat("#,##0.00",
        DecimalFormatSymbols(Locale.US)).format(value.toBigDecimal())
fun percent(value: String?): String = if (value == null) "Unavailable"
    else (if (value.toBigDecimal().signum() > 0) "+" else "") + amount(value) + "%"
