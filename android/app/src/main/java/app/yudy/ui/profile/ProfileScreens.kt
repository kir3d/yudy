package app.yudy.ui.profile

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import app.yudy.R
import app.yudy.domain.auth.AuthUser
import app.yudy.domain.profile.TaxonomyItem
import app.yudy.ui.auth.AuthViewModel
import app.yudy.ui.risk.RiskGate
import app.yudy.ui.risk.RiskResultCard
import app.yudy.ui.theme.YudyColors

@Composable
fun ProfileFlow(user: AuthUser, auth: AuthViewModel, onConsentRequired: () -> Unit, onDiscover: () -> Unit) {
    val model: ProfileViewModel = viewModel()
    val state by model.state.collectAsStateWithLifecycle()
    val authState by auth.state.collectAsStateWithLifecycle()
    LaunchedEffect(user.id) { model.bindUser(user.id) }
    DisposableEffect(user.id) { onDispose { model.clear() } }
    LaunchedEffect(state.consentRequired) { if (state.consentRequired) onConsentRequired() }
    BackHandler(enabled = state.busy || state.editing && (state.step > 0 || state.profile != null)) {
        if (!state.busy) { if (state.step > 0) model.back() else model.cancelEdit() }
    }
    Column(Modifier.fillMaxSize().safeDrawingPadding().verticalScroll(rememberScrollState()).padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Image(painterResource(R.drawable.yudy_mark), null, Modifier.size(40.dp))
            Column(Modifier.weight(1f)) {
                Text("YUDY // SETTINGS", style = MaterialTheme.typography.labelSmall,
                    color = YudyColors.Cyan)
                Text("Profile & preferences", style = MaterialTheme.typography.headlineSmall)
            }
            if (state.profile != null && !state.editing) TextButton(onClick = onDiscover) { Text("Done") }
        }
        HorizontalDivider(color = YudyColors.Line)
        Text(user.email, style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (state.busy) {
            CircularProgressIndicator()
            Text(if (state.options == null) "Loading your profile…" else "Saving your profile…")
        }
        if (state.options != null) {
            if (state.editing) {
                val titles = listOf("Tell us about you", "What are your goals?", "Your investment horizon",
                    "What interests you?", "Regions to explore", "Anything to leave out?")
                Text(titles[state.step], style = MaterialTheme.typography.headlineSmall)
                Text("Step ${state.step + 1} of 6", style = MaterialTheme.typography.labelLarge)
                LinearProgressIndicator(progress = { (state.step + 1) / 6f }, modifier = Modifier.fillMaxWidth(),
                    color = YudyColors.Cyan, trackColor = YudyColors.SurfaceVariant)
                when (state.step) {
                    0 -> RadioChoices(experienceChoices, state.draft.experience, !state.busy, model::experience)
                    1 -> MultiChoices(state.options!!.goals, state.draft.goalIds, !state.busy) { model.toggle("goals", it) }
                    2 -> RadioChoices(horizonChoices, state.draft.horizon, !state.busy, model::horizon)
                    3 -> { Text("Choose the topics you want to explore. You can skip this step.")
                        MultiChoices(state.options!!.interests, state.draft.interestIds, !state.busy) { model.toggle("interests", it) } }
                    4 -> { Text("Choose any regions, or continue without a preference.")
                        MultiChoices(state.options!!.regions, state.draft.regionIds, !state.busy) { model.toggle("regions", it) } }
                    5 -> { Text("Optional. Choosing a topic here removes it from your interests.")
                        MultiChoices(state.options!!.interests, state.draft.excludedInterestIds, !state.busy) { model.toggle("excluded", it) } }
                }
                Button(onClick = { if (state.step == 5) model.save() else model.next() },
                    enabled = state.canContinue && (state.step < 5 || !app.yudy.ui.cache.LocalCachedReadOnly.current), modifier = Modifier.fillMaxWidth()) {
                    Text(if (state.step == 5) "Save profile" else "Continue")
                }
                if (state.step > 0) TextButton(onClick = model::back, enabled = !state.busy) { Text("Back") }
                if (state.profile != null) TextButton(onClick = model::cancelEdit, enabled = !state.busy) { Text("Cancel changes") }
            } else {
                RiskGate(user, auth, onConsentRequired) { risk, retake ->
                val profile = state.profile!!
                Text("Investor Profile", style = MaterialTheme.typography.headlineMedium)
                Text("Your preferences help YUDY select topics for exploration.")
                Button(onClick = onDiscover, modifier = Modifier.fillMaxWidth()) { Text("Explore For You") }
                RiskResultCard(risk)
                TextButton(onClick = retake, enabled = !app.yudy.ui.cache.LocalCachedReadOnly.current) { Text("Reassess Risk Profile") }
                Summary("Experience", experienceChoices[profile.experience] ?: profile.experience)
                Summary("Horizon", horizonChoices[profile.horizon] ?: profile.horizon)
                fun titles(items: List<TaxonomyItem>, ids: Set<String>) =
                    ids.joinToString { id -> items.find { it.id == id }?.title ?: "Unavailable selection" }.ifEmpty { "No preference" }
                Summary("Goals", titles(state.options!!.goals, profile.goalIds))
                Summary("Interests", titles(state.options!!.interests, profile.interestIds))
                Summary("Regions", titles(state.options!!.regions, profile.regionIds))
                Summary("Not interested", titles(state.options!!.interests, profile.excludedInterestIds))
                Button(onClick = model::edit, enabled = !state.busy && !app.yudy.ui.cache.LocalCachedReadOnly.current, modifier = Modifier.fillMaxWidth()) { Text("Edit profile") }
                }
            }
        }
        state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        if (state.sessionExpired) Button(onClick = { auth.restore() }) { Text("Sign in again") }
        else if (state.error != null || state.options == null && !state.busy || state.options?.goals?.isEmpty() == true) {
            TextButton(onClick = model::reload, enabled = !state.busy) { Text("Reload profile") }
        }
        authState.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
    }
}

@Composable
private fun Summary(label: String, value: String) {
    Card(Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = YudyColors.Surface),
        border = BorderStroke(1.dp, YudyColors.Line)) {
        Column(Modifier.padding(16.dp)) {
            Text(label.uppercase(), style = MaterialTheme.typography.labelSmall, color = YudyColors.Cyan)
            Text(value, style = MaterialTheme.typography.bodyLarge)
        }
    }
}

@Composable
private fun RadioChoices(choices: Map<String, String>, selected: String, enabled: Boolean, select: (String) -> Unit) {
    Column(Modifier.selectableGroup()) {
    choices.forEach { (code, title) ->
        Row(Modifier.fillMaxWidth().heightIn(min = 48.dp).selectable(selected == code, enabled = enabled, role = Role.RadioButton,
            onClick = { select(code) }).padding(vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
            RadioButton(selected == code, onClick = null, enabled = enabled)
            Text(title, Modifier.padding(start = 12.dp))
        }
    }
    }
}

@Composable
private fun MultiChoices(items: List<TaxonomyItem>, selected: Set<String>, enabled: Boolean, toggle: (String) -> Unit) {
    if (items.isEmpty()) Text("No options are available. Reload your profile to try again.")
    items.forEach { item ->
        Row(Modifier.fillMaxWidth().heightIn(min = 48.dp).toggleable(item.id in selected, enabled = enabled, role = Role.Checkbox,
            onValueChange = { toggle(item.id) }).padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            Checkbox(item.id in selected, onCheckedChange = null, enabled = enabled)
            Text(item.title, Modifier.padding(start = 12.dp))
        }
    }
}
