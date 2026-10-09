package app.yudy

import app.yudy.domain.legal.ConsentSnapshot
import app.yudy.domain.legal.LegalDocument
import app.yudy.domain.legal.LegalRepository
import app.yudy.ui.legal.LegalViewModel
import java.io.IOException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

private fun documents() = listOf(
    "terms" to "TERMS_OF_USE",
    "privacy" to "PRIVACY_POLICY",
    "data" to "PERSONAL_DATA_CONSENT",
).map { (id, type) ->
    LegalDocument(id, type, "version-1", id, "Document text", true, false, null)
}

private class FakeLegalRepository : LegalRepository {
    var snapshot = ConsentSnapshot(documents(), false)
    var acceptCalls = 0
    var failure: IOException? = null
    var pending: CompletableDeferred<ConsentSnapshot>? = null
    override suspend fun load(): ConsentSnapshot {
        failure?.let { throw it }
        return pending?.await() ?: snapshot
    }
    override suspend fun accept(documents: List<LegalDocument>): ConsentSnapshot {
        acceptCalls++
        failure?.let { throw it }
        snapshot = ConsentSnapshot(snapshot.documents.map {
            if (documents.any { doc -> doc.id == it.id }) it.copy(accepted = true, acceptedAt = "timestamp") else it
        }, true)
        return snapshot
    }
}

@OptIn(ExperimentalCoroutinesApi::class)
class LegalViewModelTest {
    @Before fun setup() { Dispatchers.setMain(UnconfinedTestDispatcher()) }
    @After fun cleanup() { Dispatchers.resetMain() }

    @Test fun oneActionAcceptsAllCurrentMandatoryDocuments() {
        val repository = FakeLegalRepository()
        val model = LegalViewModel(repository)
        model.bindUser("user-1")
        assertTrue(model.state.value.canAccept)
        assertFalse(model.state.value.complete)
        model.accept()
        assertEquals(1, repository.acceptCalls)
        assertTrue(model.state.value.complete)
    }

    @Test fun documentLinkOpensServerTextWithoutAccepting() {
        val repository = FakeLegalRepository()
        val model = LegalViewModel(repository)
        model.bindUser("user-1")

        model.openDocument("TERMS_OF_USE")

        assertEquals("Document text", model.state.value.openedDocument?.content)
        assertEquals(0, repository.acceptCalls)
        model.closeDocument()
        assertNull(model.state.value.openedDocument)
    }

    @Test fun failedSaveDoesNotOpenProtectedScreen() {
        val repository = FakeLegalRepository()
        val model = LegalViewModel(repository)
        model.bindUser("user-1")
        repository.failure = IOException("offline")
        model.accept()
        assertFalse(model.state.value.complete)
        assertNotNull(model.state.value.error)
        repository.failure = null
        model.accept()
        assertTrue(model.state.value.complete)
    }

    @Test fun newVersionMustBeAcceptedAgain() {
        val repository = FakeLegalRepository()
        val model = LegalViewModel(repository)
        model.bindUser("user-1")
        model.accept()
        assertTrue(model.state.value.complete)
        repository.snapshot = ConsentSnapshot(documents().map { it.copy(version = "version-2") }, false)
        model.reload()
        assertFalse(model.state.value.complete)
        assertTrue(model.state.value.canAccept)
    }

    @Test fun clearedSessionDiscardsLateResponse() {
        val repository = FakeLegalRepository().apply { pending = CompletableDeferred() }
        val model = LegalViewModel(repository)
        model.bindUser("user-1")
        model.clear()
        repository.pending!!.complete(ConsentSnapshot(documents(), true))
        assertFalse(model.state.value.complete)
        assertTrue(model.state.value.documents.isEmpty())
    }

    @Test fun alreadyAcceptedDocumentsAreNotSubmittedAgain() {
        val repository = FakeLegalRepository().apply {
            snapshot = ConsentSnapshot(documents().map {
                if (it.id == "terms") it.copy(accepted = true, acceptedAt = "timestamp") else it
            }, false)
        }
        val model = LegalViewModel(repository)
        model.bindUser("user-1")
        assertTrue(model.state.value.canAccept)
        model.accept()
        assertTrue(model.state.value.complete)
    }

    @Test fun missingDocumentsFailClosed() {
        val repository = FakeLegalRepository().apply { snapshot = ConsentSnapshot(emptyList(), false) }
        val model = LegalViewModel(repository)
        model.bindUser("user-1")
        assertFalse(model.state.value.complete)
        assertFalse(model.state.value.canAccept)
    }
}
