package app.yudy.ui.risk

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import app.yudy.domain.auth.AuthUser
import app.yudy.domain.risk.RiskResult
import app.yudy.ui.auth.AuthViewModel
import app.yudy.ui.theme.YudyColors

@Composable
fun RiskGate(user: AuthUser, auth: AuthViewModel, onConsentRequired: () -> Unit,
    profile: @Composable (RiskResult, () -> Unit) -> Unit,
) {
    val model: RiskViewModel = viewModel()
    val state by model.state.collectAsStateWithLifecycle()
    LaunchedEffect(user.id) { model.bindUser(user.id) }
    DisposableEffect(user.id) { onDispose { model.clear() } }
    LaunchedEffect(state.consentRequired) { if (state.consentRequired) onConsentRequired() }
    BackHandler(enabled = state.busy || state.editing && (state.step > 0 || state.canCancel)) {
        if (!state.busy) { if (state.step > 0) model.back() else model.cancel() }
    }
    if (!state.editing && !state.showResult && state.result != null) {
        profile(state.result!!, model::retake)
        if (state.busy) CircularProgressIndicator()
    } else if (state.showResult && state.result != null) {
        Text("Your Risk Profile", style = MaterialTheme.typography.headlineMedium)
        RiskResultCard(state.result!!)
        Button(onClick = model::continueToProfile, modifier = Modifier.fillMaxWidth()) { Text("Continue to Investor Profile") }
    } else {
        Text("Your comfort with uncertainty", style = MaterialTheme.typography.headlineSmall)
        Text("Answer based on how you feel today. Every question needs one answer.")
        if (state.result != null && (state.result?.isCurrent == false || state.result?.version != state.questionnaire?.version))
            Text("The questionnaire has changed. Complete the current version to update your profile.")
        if (state.busy) { CircularProgressIndicator(); Text("Loading or saving your assessment…") }
        val question = state.question
        if (question != null) {
            val count = state.questionnaire!!.questions.size
            Text("Question ${state.step + 1} of $count", style = MaterialTheme.typography.labelLarge)
            LinearProgressIndicator(progress = { (state.step + 1f) / count }, modifier = Modifier.fillMaxWidth(),
                color = YudyColors.Cyan, trackColor = YudyColors.SurfaceVariant)
            Text(question.text, style = MaterialTheme.typography.titleLarge)
            Column(Modifier.selectableGroup()) {
                question.options.forEach { option ->
                    val selected = state.answers[question.id] == option.id
                    Row(Modifier.fillMaxWidth().heightIn(min = 48.dp).selectable(selected,
                        enabled = !state.busy && !state.reloadRequired, role = Role.RadioButton,
                        onClick = { model.select(option.id) }).padding(vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically) {
                        RadioButton(selected, onClick = null, enabled = !state.busy && !state.reloadRequired)
                        Text(option.text, Modifier.padding(start = 12.dp))
                    }
                }
            }
            val last = state.step == count - 1
            Button(onClick = { if (last) model.submit() else model.next() },
                enabled = if (last) state.canSubmit && !app.yudy.ui.cache.LocalCachedReadOnly.current else state.canContinue,
                modifier = Modifier.fillMaxWidth()) { Text(if (last) "See my result" else "Continue") }
            if (state.step > 0) TextButton(onClick = model::back, enabled = !state.busy) { Text("Back") }
            if (state.canCancel) TextButton(onClick = model::cancel) { Text("Cancel reassessment") }
        } else if (!state.busy && state.error == null) {
            Text("No questions are available. Please reload the questionnaire.")
            TextButton(onClick = model::reload) { Text("Reload questionnaire") }
        }
        Text("This internal YUDY questionnaire describes your preferences for exploration. It does not assess an individual asset or provide personal investment advice.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
    state.error?.let {
        Text(it, color = MaterialTheme.colorScheme.error)
        if (state.sessionExpired) Button(onClick = { auth.restore() }) { Text("Sign in again") }
        else TextButton(onClick = model::reload, enabled = !state.busy) { Text("Reload questionnaire") }
    }
}

@Composable
fun RiskResultCard(result: RiskResult) {
    Card(Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = YudyColors.Surface),
        border = BorderStroke(1.dp, YudyColors.Line)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("RISK PROFILE", style = MaterialTheme.typography.labelSmall, color = YudyColors.Cyan)
            Text(result.category, style = MaterialTheme.typography.headlineSmall)
            Text("${result.score} / 100", style = MaterialTheme.typography.titleMedium)
            Text("Based on your answers · ${result.version}", style = MaterialTheme.typography.bodySmall)
            Text("A personalization signal for exploration. Individual asset risks are shown separately.",
                style = MaterialTheme.typography.bodySmall)
        }
    }
}
