package app.yudy

import app.yudy.domain.profile.*
import app.yudy.ui.profile.ProfileViewModel
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

private class FakeProfileRepository : ProfileRepository {
    var profile: InvestorProfile? = null
    var failure: Exception? = null
    var pending: CompletableDeferred<InvestorProfile?>? = null
    var saves = 0
    var onboarding: Boolean? = null
    override suspend fun options() = ProfileOptions(listOf(TaxonomyItem("goal", "growth", "Growth")),
        listOf(TaxonomyItem("interest", "ai", "AI")), listOf(TaxonomyItem("region", "usa", "USA")))
    override suspend fun load(): InvestorProfile? = pending?.await() ?: profile
    override suspend fun save(profile: InvestorProfile, onboarding: Boolean): InvestorProfile {
        saves++
        this.onboarding = onboarding
        failure?.let { throw it }
        this.profile = profile
        return profile
    }
}

@OptIn(ExperimentalCoroutinesApi::class)
class ProfileViewModelTest {
    @Before fun setup() { Dispatchers.setMain(UnconfinedTestDispatcher()) }
    @After fun cleanup() { Dispatchers.resetMain() }
    private fun complete(model: ProfileViewModel) {
        model.experience("NEW"); model.next()
        model.toggle("goals", "goal"); model.next()
        model.horizon("FIVE_PLUS"); model.next()
        model.toggle("interests", "interest"); model.next()
        model.toggle("regions", "region"); model.next()
    }
    @Test fun requiredStepsCannotBeSkippedAndProfileAppearsOnlyAfterSave() {
        val repository = FakeProfileRepository()
        val model = ProfileViewModel(repository)
        model.bindUser("user-1")
        model.next(); model.save()
        assertEquals(0, model.state.value.step)
        assertEquals(0, repository.saves)
        model.experience("NEW"); model.next(); model.next()
        assertEquals(1, model.state.value.step)
        model.toggle("goals", "goal"); model.next(); model.next()
        assertEquals(2, model.state.value.step)
        model.horizon("FIVE_PLUS"); model.next(); model.next(); model.next()
        assertNull(model.state.value.profile)
        model.save()
        assertEquals(true, repository.onboarding)
        assertFalse(model.state.value.editing)
        assertNotNull(model.state.value.profile)
    }
    @Test fun interestAndExcludedInterestAreMutuallyExclusive() {
        val model = ProfileViewModel(FakeProfileRepository())
        model.bindUser("user")
        model.toggle("interests", "interest")
        model.toggle("excluded", "interest")
        assertTrue(model.state.value.draft.interestIds.isEmpty())
        assertEquals(setOf("interest"), model.state.value.draft.excludedInterestIds)
        model.toggle("interests", "interest")
        assertTrue(model.state.value.draft.excludedInterestIds.isEmpty())
        model.toggle("goals", "unknown")
        assertTrue(model.state.value.draft.goalIds.isEmpty())
    }
    @Test fun failedSaveKeepsDraftAndAllowsRetry() {
        val repository = FakeProfileRepository()
        val model = ProfileViewModel(repository)
        model.bindUser("user"); complete(model)
        val draft = model.state.value.draft
        repository.failure = IOException("offline")
        model.save()
        assertTrue(model.state.value.editing)
        assertNull(model.state.value.profile)
        assertEquals(draft, model.state.value.draft)
        assertNotNull(model.state.value.error)
        repository.failure = null; model.save()
        assertEquals(draft, model.state.value.profile)
    }
    @Test fun editingCanBeCancelledAndUsesUpdateInsteadOfOnboarding() {
        val repository = FakeProfileRepository()
        val model = ProfileViewModel(repository)
        model.bindUser("user"); complete(model); model.save()
        val original = model.state.value.profile
        model.edit(); model.experience("SOME"); model.cancelEdit()
        assertEquals(original, model.state.value.profile)
        assertEquals(original, model.state.value.draft)
        model.edit(); model.experience("EXPERIENCED")
        repeat(5) { model.next() }; model.save()
        assertEquals(false, repository.onboarding)
        assertEquals("EXPERIENCED", model.state.value.profile!!.experience)
    }
    @Test fun newLegalRequirementDoesNotConfirmProfileSave() {
        val repository = FakeProfileRepository()
        val model = ProfileViewModel(repository)
        model.bindUser("user"); complete(model)
        repository.failure = HttpException(Response.error<Any>(403, "{}".toResponseBody()))
        model.save()
        assertTrue(model.state.value.consentRequired)
        assertNull(model.state.value.profile)
    }
    @Test fun accountSwitchCancelsPreviousResponseAndClearsDraft() {
        val repository = FakeProfileRepository().apply { pending = CompletableDeferred() }
        val model = ProfileViewModel(repository)
        model.bindUser("first")
        val old = repository.pending!!
        repository.pending = null
        model.bindUser("second")
        old.complete(InvestorProfile("EXPERIENCED", "FIVE_PLUS", setOf("goal")))
        assertNull(model.state.value.profile)
        assertEquals("", model.state.value.draft.experience)
        assertFalse(model.state.value.busy)
    }
    @Test fun inactiveSelectionsAreRemovedOnlyFromEditableDraft() {
        val repository = FakeProfileRepository().apply {
            profile = InvestorProfile("NEW", "FIVE_PLUS", setOf("inactive"))
        }
        val model = ProfileViewModel(repository)
        model.bindUser("user"); model.edit()
        assertTrue(model.state.value.draft.goalIds.isEmpty())
        assertEquals(setOf("inactive"), model.state.value.profile!!.goalIds)
        assertNotNull(model.state.value.error)
    }
}
