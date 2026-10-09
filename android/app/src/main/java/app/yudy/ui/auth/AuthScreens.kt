package app.yudy.ui.auth

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import app.yudy.R
import app.yudy.ui.legal.LegalGate
import app.yudy.ui.theme.YudyColors

@Composable
fun AuthNavigation(model: AuthViewModel,
    welcome: @Composable (() -> Unit, () -> Unit) -> Unit,
) {
    val state by model.state.collectAsStateWithLifecycle()
    app.yudy.ui.cache.OfflineContainer {
    Surface(Modifier.fillMaxSize()) {
        when {
            state.user != null -> LegalGate(state.user!!, model) { reloadConsent ->
                var discover by remember(state.user!!.id) { mutableStateOf(true) }
                if (discover) app.yudy.ui.assets.DiscoverFlow(state.user!!, model, reloadConsent) { discover = false }
                else app.yudy.ui.profile.ProfileFlow(state.user!!, model, reloadConsent) { discover = true }
            }
            state.restoring -> AuthPage {
                if (state.busy) {
                    CircularProgressIndicator()
                    Text("Checking your session…")
                } else {
                    Text(state.error ?: "Couldn’t restore your session.",
                        color = MaterialTheme.colorScheme.error)
                    Button(onClick = { model.restore() }) { Text("Retry") }
                }
            }
            else -> {
                val nav = rememberNavController()
                NavHost(navController = nav, startDestination = "welcome") {
                    composable("welcome") {
                        welcome({ nav.navigate("register") }, { nav.navigate("login") })
                    }
                    composable("register") {
                        AuthForm(state, model, register = true,
                            back = { nav.popBackStack() },
                            switch = { nav.navigate("login") { popUpTo("welcome") } })
                    }
                    composable("login") {
                        AuthForm(state, model, register = false,
                            back = { nav.popBackStack() },
                            switch = { nav.navigate("register") { popUpTo("welcome") } })
                    }
                }
            }
        }
    }
}

}

@Composable
private fun AuthPage(content: @Composable ColumnScope.() -> Unit) {
    Box(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(
        YudyColors.Surface, YudyColors.Midnight, YudyColors.Midnight,
    )))) {
        Column(Modifier.fillMaxSize().safeDrawingPadding().imePadding()
            .verticalScroll(rememberScrollState()).padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(18.dp),
            horizontalAlignment = Alignment.Start,
        ) {
            Row(verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Image(painterResource(R.drawable.yudy_mark), contentDescription = null,
                    modifier = Modifier.size(42.dp))
                Column {
                    Text("YUDY", style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold)
                    Text("DISCOVERY NETWORK", style = MaterialTheme.typography.labelSmall,
                        color = YudyColors.Cyan)
                }
            }
            HorizontalDivider(color = YudyColors.Line)
            Spacer(Modifier.height(8.dp))
            content()
        }
    }
}

@Composable
private fun AuthForm(state: AuthUiState, model: AuthViewModel, register: Boolean,
    back: () -> Unit, switch: () -> Unit,
) {
    var showPassword by remember { mutableStateOf(false) }
    LaunchedEffect(register) { model.clearForm() }
    DisposableEffect(register) { onDispose { model.clearForm() } }
    BackHandler(enabled = state.busy) { }
    AuthPage {
        Text(if (register) "CREATE YOUR ACCESS" else "WELCOME BACK",
            style = MaterialTheme.typography.labelSmall, color = YudyColors.Cyan)
        Text(if (register) "Create your account" else "Welcome back",
            style = MaterialTheme.typography.headlineMedium)
        OutlinedTextField(value = state.email, onValueChange = model::emailChanged,
            label = { Text("Email") }, singleLine = true, enabled = !state.busy,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email,
                imeAction = ImeAction.Next), modifier = Modifier.fillMaxWidth())
        OutlinedTextField(value = state.password, onValueChange = model::passwordChanged,
            label = { Text("Password") }, singleLine = true, enabled = !state.busy,
            supportingText = { Text("10–128 characters") },
            visualTransformation = if (showPassword) VisualTransformation.None else PasswordVisualTransformation(),
            trailingIcon = {
                TextButton(onClick = { showPassword = !showPassword }) {
                    Text(if (showPassword) "Hide" else "Show")
                }
            },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password,
                imeAction = ImeAction.Done),
            keyboardActions = KeyboardActions(onDone = { model.submit(register) }),
            modifier = Modifier.fillMaxWidth())
        state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        Button(onClick = { model.submit(register) }, enabled = !state.busy,
            modifier = Modifier.fillMaxWidth()) {
            Text(if (register) "Create account" else "Sign in")
        }
        if (state.busy) CircularProgressIndicator()
        TextButton(onClick = switch, enabled = !state.busy) {
            Text(if (register) "Already registered? Sign in" else "New here? Create account")
        }
        TextButton(onClick = { model.clearForm(); back() }, enabled = !state.busy) { Text("Back") }
        Text("YUDY helps you discover what to explore. It does not execute trades or provide personal investment advice.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
