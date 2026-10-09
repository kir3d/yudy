package app.yudy

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.By
import androidx.test.uiautomator.UiDevice
import androidx.test.uiautomator.Until
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.util.UUID
import java.net.HttpURLConnection
import java.net.URL

/** Requires the local demo backend and provider reachable at the configured debug URL. */
@RunWith(AndroidJUnit4::class)
class DiscoveryJourneyTest {
    @get:Rule val ui = createAndroidComposeRule<MainActivity>()
    private val device get() = UiDevice.getInstance(InstrumentationRegistry.getInstrumentation())

    private fun awaitText(text: String) {
        try {
            ui.waitUntil(60_000) { ui.onAllNodesWithText(text).fetchSemanticsNodes().isNotEmpty() }
        } catch (error: ComposeTimeoutException) {
            device.executeShellCommand("screencap -p /data/local/tmp/yudy-test-failure.png")
            throw AssertionError("Timed out waiting for: $text", error)
        }
    }
    private fun click(text: String) {
        awaitText(text)
        val target = hasText(text) and !hasSetTextAction()
        ui.waitUntil(60_000) { ui.onAllNodes(target and isEnabled()).fetchSemanticsNodes().isNotEmpty() }
        val node = ui.onAllNodes(target).onFirst()
        try { node.performScrollTo() } catch (_: AssertionError) { }
        node.performClick()
    }
    private fun firstChoice() {
        ui.onAllNodes(isSelectable() and hasClickAction()).onFirst().performScrollTo().performClick()
    }
    private fun screenshot(name: String) {
        ui.waitForIdle()
        device.executeShellCommand("screencap -p /data/local/tmp/yudy-$name.png")
    }
    private fun apiReachable() = runCatching {
        val connection = URL(BuildConfig.API_BASE_URL + "health").openConnection() as HttpURLConnection
        try {
            connection.connectTimeout = 500; connection.readTimeout = 500
            connection.responseCode == 200
        } finally { connection.disconnect() }
    }.getOrDefault(false)

    @Test fun registerToExternalProviderAndBack() {
        val email = "android-${UUID.randomUUID()}@example.com"
        click("Get started")
        ui.onNodeWithText("Email").performTextInput(email)
        ui.onNodeWithText("Password").performTextInput("Local-device-test-42")
        click("Create account")
        awaitText("Before we continue")
        ui.waitUntil(30_000) { ui.onAllNodes(isToggleable() and hasClickAction()).fetchSemanticsNodes().size == 3 }
        ui.onNodeWithText("Accept and continue").assertIsNotEnabled()
        repeat(3) { ui.onAllNodes(isToggleable() and hasClickAction())[it].performScrollTo().performClick() }
        click("Accept and continue")
        awaitText("Tell us about you"); firstChoice(); click("Continue")
        awaitText("What are your goals?")
        ui.onAllNodes(isToggleable() and hasClickAction()).onFirst().performScrollTo().performClick()
        click("Continue")
        awaitText("Your investment horizon"); firstChoice(); click("Continue")
        awaitText("What interests you?")
        ui.onAllNodes(isToggleable() and hasClickAction()).onFirst().performScrollTo().performClick()
        click("Continue")
        awaitText("Regions to explore")
        ui.onAllNodes(isToggleable() and hasClickAction()).onFirst().performScrollTo().performClick()
        click("Continue")
        awaitText("Anything to leave out?"); click("Save profile")
        repeat(7) { index ->
            awaitText("Question ${index + 1} of 7")
            firstChoice(); click(if(index == 6) "See my result" else "Continue")
        }
        click("Continue to Investor Profile"); click("Explore For You")
        awaitText("Why you’re seeing this"); click("Why you’re seeing this")
        awaitText("Hide reasons")
        screenshot("for-you")
        click("Discover")
        ui.onNodeWithText("Search symbol or name").performTextInput("DM01")
        click("Search"); click("DM01")
        awaitText("Your actions")
        ui.waitUntil(30_000) { ui.onAllNodes(hasText("Like") and isEnabled()).fetchSemanticsNodes().isNotEmpty() }
        click("Like")
        ui.waitUntil(30_000) { ui.onAllNodes(hasText("Save") and isEnabled()).fetchSemanticsNodes().isNotEmpty() }
        click("Save"); awaitText("Saved · Remove")
        device.pressBack(); click("Saved"); click("DM01")
        awaitText("Saved · Remove")
        screenshot("asset")
        click("BUY")
        ui.waitUntil(30_000) { ui.onAllNodes(hasText("DM01-TA", substring = true) and hasClickAction()).fetchSemanticsNodes().isNotEmpty() }
        ui.onAllNodes(hasText("DM01-TA", substring = true) and hasClickAction()).onFirst().performClick()
        awaitText("Open provider demo")
        click("Cancel")
        click("BUY")
        ui.onAllNodes(hasText("DM01-TA", substring = true) and hasClickAction()).onFirst().performClick()
        click("Open provider demo")
        // Complete the browser's first-run setup before running this journey.
        ui.waitUntil(30_000) { device.currentPackageName?.let { it != "app.yudy" } == true }
        assertTrue("External demo page did not load", device.wait(
            Until.hasObject(By.textContains("No transaction has been performed")), 30_000))
        screenshot("external-browser")
        device.pressBack()
        awaitText("Back to Saved")
        device.pressBack(); click("Discover"); click("Learn")
        click("What are tokenized stocks?")
        awaitText("Back to Learn")
        screenshot("learn")
        device.pressBack(); awaitText("Understand the terms behind the asset pages.")
        device.pressBack(); click("Saved"); awaitText("DM01")
        try {
            device.executeShellCommand("svc wifi disable")
            device.executeShellCommand("svc data disable")
            ui.waitUntil(30_000) { !apiReachable() }
            click("Refresh Saved")
            awaitText("Cached data · read only")
            click("DM01")
            awaitText("BUY")
            ui.onNodeWithText("BUY").assertIsNotEnabled()
            ui.onNodeWithText("Like").assertIsNotEnabled()
            screenshot("offline")
        } finally {
            device.executeShellCommand("svc wifi enable")
            device.executeShellCommand("svc data enable")
        }
        ui.waitUntil(30_000) { apiReachable() }
        click("Reconnect and reload")
        awaitText("Investor Profile")
        ui.onNodeWithText("Cached data · read only").assertDoesNotExist()
        click("Sign out")
        click("Already have an account? Sign in")
        ui.onNodeWithText("Email").performTextReplacement(email)
        ui.onNodeWithText("Password").performTextInput("Local-device-test-42")
        click("Sign in")
        awaitText("Investor Profile")
        screenshot("investor-profile")
    }
}
