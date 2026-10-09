package app.yudy.ui.legal

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.LinkAnnotation
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextLinkStyles
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.withLink
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import app.yudy.R
import app.yudy.domain.auth.AuthUser
import app.yudy.domain.legal.LegalDocument
import app.yudy.ui.auth.AuthViewModel
import app.yudy.ui.theme.YudyColors

@Composable
fun LegalGate(user: AuthUser, auth: AuthViewModel, afterConsent: @Composable (() -> Unit) -> Unit) {
    val model: LegalViewModel = viewModel()
    val state by model.state.collectAsStateWithLifecycle()
    LaunchedEffect(user.id) { model.bindUser(user.id) }
    DisposableEffect(user.id) { onDispose { model.clear() } }
    if (state.complete) {
        afterConsent(model::reload)
        return
    }
    if (state.busy && state.documents.isEmpty() && state.error == null) {
        Box(
            Modifier.fillMaxSize().background(YudyColors.Midnight),
            contentAlignment = Alignment.Center,
        ) {
            CircularProgressIndicator(color = YudyColors.Cyan)
        }
        return
    }
    state.openedDocument?.let { document ->
        LegalDocumentScreen(document, model::closeDocument)
        return
    }
    Box(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(
        YudyColors.Surface, YudyColors.Midnight, YudyColors.Midnight,
    )))) {
        Column(Modifier.fillMaxSize().safeDrawingPadding().verticalScroll(rememberScrollState())
            .padding(24.dp), verticalArrangement = Arrangement.spacedBy(18.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Image(painterResource(R.drawable.yudy_mark), null, Modifier.size(40.dp))
                Column {
                    Text("YUDY", style = MaterialTheme.typography.titleLarge)
                    Text("TERMS // CURRENT VERSION", style = MaterialTheme.typography.labelSmall,
                        color = YudyColors.Cyan)
                }
            }
            HorizontalDivider(color = YudyColors.Line)
            Spacer(Modifier.height(18.dp))
            Text("Before we continue", style = MaterialTheme.typography.displaySmall)
            LegalAgreementSentence(model::openDocument)
            Spacer(Modifier.height(8.dp))
            if (state.busy) CircularProgressIndicator()
            if (!state.busy && state.documents.isEmpty() && state.error == null) {
                Text("Required documents are unavailable. Please try again later.")
            }
            state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            if (state.sessionExpired) {
                Button(onClick = { auth.restore() }) { Text("Sign in again") }
            } else {
                Button(onClick = model::accept, enabled = state.canAccept && !app.yudy.ui.cache.LocalCachedReadOnly.current,
                    modifier = Modifier.fillMaxWidth()) { Text("Accept and continue") }
                TextButton(onClick = model::reload, enabled = !state.busy) { Text("Reload documents") }
            }
            val authState by auth.state.collectAsStateWithLifecycle()
            authState.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            TextButton(onClick = auth::logout, enabled = !state.busy && !authState.busy) {
                Text("Sign out without accepting")
            }
        }
    }
}

@Composable
private fun LegalAgreementSentence(openDocument: (String) -> Unit) {
    val linkStyle = TextLinkStyles(SpanStyle(
        color = YudyColors.Cyan,
        fontWeight = FontWeight.SemiBold,
        textDecoration = TextDecoration.Underline,
    ))
    val text = buildAnnotatedString {
        append("By tapping Accept and continue, you accept the current ")
        withLink(LinkAnnotation.Clickable("TERMS_OF_USE", linkStyle) {
            openDocument("TERMS_OF_USE")
        }) { append("Terms of Use") }
        append(", ")
        withLink(LinkAnnotation.Clickable("PRIVACY_POLICY", linkStyle) {
            openDocument("PRIVACY_POLICY")
        }) { append("Privacy Policy") }
        append(" and ")
        withLink(LinkAnnotation.Clickable("PERSONAL_DATA_CONSENT", linkStyle) {
            openDocument("PERSONAL_DATA_CONSENT")
        }) { append("Consent to Personal Data Processing") }
        append(".")
    }
    Text(text, color = YudyColors.Muted, style = MaterialTheme.typography.bodyLarge)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun LegalDocumentScreen(document: LegalDocument, back: () -> Unit) {
    BackHandler(onBack = back)
    Scaffold(containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            TopAppBar(
                title = { Text(document.title) },
                navigationIcon = {
                    IconButton(onClick = back) {
                        Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Back to agreements")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background),
            )
        }) { insets ->
        LazyColumn(Modifier.fillMaxSize().padding(insets).padding(horizontal = 24.dp),
            verticalArrangement = Arrangement.spacedBy(18.dp),
            contentPadding = PaddingValues(top = 12.dp, bottom = 40.dp)) {
            item {
                Text("VERSION ${document.version}", style = MaterialTheme.typography.labelSmall,
                    color = YudyColors.Cyan)
            }
            document.content.split("\n\n").filter { it.isNotBlank() }.forEachIndexed { index, block ->
                item {
                    val lines = block.lines()
                    when {
                        index == 0 -> Text(block, style = MaterialTheme.typography.labelSmall,
                            color = YudyColors.Cyan)
                        lines.size > 1 -> Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text(lines.first(), style = MaterialTheme.typography.titleMedium)
                            Text(lines.drop(1).joinToString("\n"), style = MaterialTheme.typography.bodyMedium,
                                color = YudyColors.Muted)
                        }
                        else -> Text(block, style = MaterialTheme.typography.bodyMedium,
                            color = YudyColors.Muted)
                    }
                }
            }
        }
    }
}
