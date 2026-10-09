package app.yudy

import app.yudy.domain.auth.SessionExpiredException
import app.yudy.domain.risk.*
import app.yudy.ui.risk.RiskViewModel
import java.io.IOException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import retrofit2.HttpException
import retrofit2.Response

private fun riskQuestions(version: String = "v1") = RiskQuestionnaire(version, (1..2).map { id ->
    RiskQuestion("q$id", "code$id", "Question $id", listOf(RiskOption("q$id-low", "Lower"), RiskOption("q$id-high", "Higher")))
})
private class FakeRiskRepository : RiskRepository {
    var questionnaire = riskQuestions()
    var result: RiskResult? = null
    var failure: Exception? = null
    var loadFailure: Exception? = null
    var pending: CompletableDeferred<RiskResult?>? = null
    var pendingSave: CompletableDeferred<RiskResult>? = null
    var submissions = 0
    var submittedVersion: String? = null
    var submittedAnswers: Map<String, String>? = null
    override suspend fun questions() = questionnaire
    override suspend fun load(): RiskResult? {
        loadFailure?.let { throw it }
        return pending?.await() ?: result
    }
    override suspend fun assess(version: String, answers: Map<String, String>): RiskResult {
        submissions++; submittedVersion = version; submittedAnswers = answers
        failure?.let { throw it }
        result = pendingSave?.await() ?: RiskResult(48, "Balanced", version, "timestamp", true)
        return result!!
    }
}

@OptIn(ExperimentalCoroutinesApi::class)
class RiskViewModelTest {
    @Before fun setup() { Dispatchers.setMain(UnconfinedTestDispatcher()) }
    @After fun cleanup() { Dispatchers.resetMain() }
    private fun answerAll(model: RiskViewModel) {
        model.select("q1-low"); model.next(); model.select("q2-high")
    }
    @Test fun cannotSkipOrSubmitMissingAnswersAndResultComesOnlyFromServer() {
        val repository = FakeRiskRepository()
        val model = RiskViewModel(repository)
        model.bindUser("user")
        model.next(); model.submit(); model.select("unknown")
        assertEquals(0, model.state.value.step)
        assertFalse(model.state.value.canContinue)
        assertEquals(0, repository.submissions)
        answerAll(model)
        assertTrue(model.state.value.canSubmit)
        assertNull(model.state.value.result)
        model.submit()
        assertEquals("v1", repository.submittedVersion)
        assertEquals(mapOf("q1" to "q1-low", "q2" to "q2-high"), repository.submittedAnswers)
        assertEquals(48, model.state.value.result!!.score)
        assertTrue(model.state.value.showResult)
        assertFalse(model.state.value.editing)
        model.continueToProfile()
        assertFalse(model.state.value.showResult)
    }
    @Test fun backPreservesAnswersAndAllowsChanges() {
        val model = RiskViewModel(FakeRiskRepository())
        model.bindUser("user"); answerAll(model); model.back()
        assertEquals("q1-low", model.state.value.answers["q1"])
        model.select("q1-high"); model.next()
        assertEquals("q2-high", model.state.value.answers["q2"])
        assertTrue(model.state.value.canSubmit)
    }
    @Test fun networkFailurePreservesAnswersAndRetryDoesNotFakeResult() {
        val repository = FakeRiskRepository()
        val model = RiskViewModel(repository)
        model.bindUser("user"); answerAll(model)
        repository.failure = IOException("offline"); model.submit()
        assertNull(model.state.value.result)
        assertTrue(model.state.value.editing)
        assertTrue(model.state.value.canSubmit)
        assertNotNull(model.state.value.error)
        repository.failure = null; model.submit()
        assertEquals(2, repository.submissions)
        assertEquals("Balanced", model.state.value.result!!.category)
    }
    @Test fun repeatedSubmitIsBlockedWhileRequestIsPending() {
        val repository = FakeRiskRepository().apply { pendingSave = CompletableDeferred() }
        val model = RiskViewModel(repository)
        model.bindUser("user"); answerAll(model); model.submit(); model.submit()
        assertTrue(model.state.value.busy)
        assertEquals(1, repository.submissions)
        repository.pendingSave!!.complete(RiskResult(0, "Conservative", "v1", "timestamp", true))
        assertFalse(model.state.value.busy)
        assertEquals("Conservative", model.state.value.result!!.category)
    }
    @Test fun currentSavedResultOpensProfileAndRetakeCanBeCancelled() {
        val saved = RiskResult(48, "Balanced", "v1", "timestamp", true)
        val repository = FakeRiskRepository().apply { result = saved }
        val model = RiskViewModel(repository)
        model.bindUser("user")
        assertFalse(model.state.value.editing)
        model.retake(); model.select("q1-high")
        assertTrue(model.state.value.canCancel)
        model.cancel()
        assertEquals(saved, model.state.value.result)
        assertFalse(model.state.value.editing)
        assertEquals(0, repository.submissions)
    }
    @Test fun outdatedProfileRequiresNewQuestionnaireAndCannotCancel() {
        val repository = FakeRiskRepository().apply {
            questionnaire = riskQuestions("v2")
            result = RiskResult(48, "Balanced", "v1", "timestamp", false)
        }
        val model = RiskViewModel(repository)
        model.bindUser("user")
        assertTrue(model.state.value.editing)
        assertFalse(model.state.value.canCancel)
        model.cancel()
        assertTrue(model.state.value.editing)
        assertTrue(model.state.value.answers.isEmpty())
        answerAll(model); model.submit()
        assertEquals("v2", model.state.value.result!!.version)
    }
    @Test fun staleSubmissionRequiresReloadAndClearsOldAnswers() {
        val repository = FakeRiskRepository()
        val model = RiskViewModel(repository)
        model.bindUser("user"); answerAll(model)
        repository.failure = HttpException(Response.error<Any>(409, "{}".toResponseBody()))
        model.submit()
        assertTrue(model.state.value.reloadRequired)
        assertFalse(model.state.value.canSubmit)
        model.submit(); assertEquals(1, repository.submissions)
        repository.failure = null; repository.questionnaire = riskQuestions("v2"); model.reload()
        assertTrue(model.state.value.answers.isEmpty())
        assertEquals("v2", model.state.value.questionnaire!!.version)
        assertFalse(model.state.value.reloadRequired)
    }
    @Test fun staleRetakeCannotReturnToAnOldProfileWithoutReloading() {
        val repository = FakeRiskRepository().apply {
            result = RiskResult(48, "Balanced", "v1", "timestamp", true)
        }
        val model = RiskViewModel(repository)
        model.bindUser("user"); model.retake(); answerAll(model)
        repository.failure = HttpException(Response.error<Any>(409, "{}".toResponseBody()))
        model.submit(); model.cancel()
        assertFalse(model.state.value.canCancel)
        assertTrue(model.state.value.editing)
        assertTrue(model.state.value.reloadRequired)
    }
    @Test fun legalAndSessionFailuresStayProtected() {
        val repository = FakeRiskRepository()
        val model = RiskViewModel(repository)
        model.bindUser("user"); answerAll(model)
        repository.failure = HttpException(Response.error<Any>(403, "{}".toResponseBody()))
        model.submit()
        assertTrue(model.state.value.consentRequired)
        assertNull(model.state.value.result)
        repository.failure = SessionExpiredException(); model.submit()
        assertTrue(model.state.value.sessionExpired)
        assertNull(model.state.value.result)
    }
    @Test fun accountSwitchCancelsLateResponseAndClearsAnswers() {
        val repository = FakeRiskRepository().apply { pending = CompletableDeferred() }
        val model = RiskViewModel(repository)
        model.bindUser("first")
        val old = repository.pending!!
        repository.pending = null; model.bindUser("second")
        old.complete(RiskResult(100, "Growth", "v1", "timestamp", true))
        assertNull(model.state.value.result)
        assertTrue(model.state.value.answers.isEmpty())
        assertFalse(model.state.value.busy)
    }
    @Test fun failedRestoreDoesNotOpenInvestorProfileAndEmptyQuestionnaireBlocksSubmit() {
        val repository = FakeRiskRepository().apply { loadFailure = IOException("offline") }
        val model = RiskViewModel(repository)
        model.bindUser("user")
        assertTrue(model.state.value.editing)
        assertNull(model.state.value.result)
        assertNotNull(model.state.value.error)
        repository.loadFailure = null; repository.questionnaire = RiskQuestionnaire("v1", emptyList())
        model.reload(); model.submit()
        assertFalse(model.state.value.canContinue)
        assertFalse(model.state.value.canSubmit)
        assertEquals(0, repository.submissions)
    }
}
