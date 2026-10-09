package app.yudy.data.learn

import app.yudy.data.auth.ApiData
import app.yudy.domain.learn.*
import com.squareup.moshi.Json
import javax.inject.Inject
import retrofit2.http.GET
import retrofit2.http.Path

data class ArticleDto(val id: String, val slug: String, val title: String, val summary: String,
    @param:Json(name = "updated_at") val updatedAt: String, val content: String? = null) {
    fun toDomain() = LearnArticle(id, slug, title, summary, updatedAt, content)
}
interface LearnApi {
    @GET("api/v1/learn/articles") suspend fun articles(): ApiData<List<ArticleDto>>
    @GET("api/v1/learn/articles/{slug}") suspend fun article(@Path("slug") slug: String): ApiData<ArticleDto>
}
class RemoteLearnRepository @Inject constructor(private val api: LearnApi): LearnRepository {
    override suspend fun articles() = api.articles().data.map { it.toDomain() }
    override suspend fun article(slug: String): LearnArticle {
        val article = api.article(slug).data.toDomain()
        check(!article.content.isNullOrBlank()) { "Article content is unavailable" }
        return article
    }
}
