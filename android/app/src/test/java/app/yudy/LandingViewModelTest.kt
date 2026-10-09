package app.yudy

import org.junit.Assert.assertTrue
import org.junit.Test

class LandingViewModelTest {
    @Test
    fun initialStateExplainsDiscoveryAndRisks() {
        val state = LandingViewModel().state.value
        assertTrue(state.title.contains("market"))
        assertTrue(state.description.contains("tokenized stocks"))
        assertTrue(state.description.contains("underneath"))
    }
}
