package app.yudy.domain.learn

data class LearnArticle(val id: String, val slug: String, val title: String, val summary: String, val updatedAt: String, val content: String? = null)
interface LearnRepository {
    suspend fun articles(): List<LearnArticle>
    suspend fun article(slug: String): LearnArticle
}
