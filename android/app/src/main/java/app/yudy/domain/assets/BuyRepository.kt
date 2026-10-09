package app.yudy.domain.assets

import java.net.URI

data class BuyLink(val provider: String, val url: String, val tokenId: String, val tokenSymbol: String, val demo: Boolean)
interface BuyRepository {
    suspend fun preview(assetId: String, tokenId: String): BuyLink
    suspend fun confirm(assetId: String, tokenId: String, eventId: String): BuyLink
}
fun validExternalBuyUrl(url: String, allowHttp: Boolean): Boolean = try {
    val uri = URI(url)
    (uri.scheme == "https" || (allowHttp && uri.scheme == "http")) &&
        !uri.host.isNullOrBlank() && uri.rawUserInfo == null && uri.rawFragment == null &&
        (uri.port == -1 || uri.port in 1..65535) && url.none { it.isWhitespace() || it.isISOControl() }
} catch(error: Exception) { false }
