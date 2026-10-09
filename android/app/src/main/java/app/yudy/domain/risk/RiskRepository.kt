package app.yudy.domain.risk

data class RiskOption(val id: String, val text: String)
data class RiskQuestion(val id: String, val code: String, val text: String, val options: List<RiskOption>)
data class RiskQuestionnaire(val version: String, val questions: List<RiskQuestion>)
data class RiskResult(val score: Int, val category: String, val version: String,
    val calculatedAt: String, val isCurrent: Boolean)
interface RiskRepository {
    suspend fun questions(): RiskQuestionnaire
    suspend fun load(): RiskResult?
    suspend fun assess(version: String, answers: Map<String, String>): RiskResult
}
