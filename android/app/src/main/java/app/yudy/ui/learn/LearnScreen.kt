package app.yudy.ui.learn

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import app.yudy.ui.theme.YudyColors

@Composable
fun LearnScreen(modifier: Modifier = Modifier) {
    val model: LearnViewModel = viewModel()
    val state by model.state.collectAsStateWithLifecycle()
    val listState = rememberLazyListState()
    LaunchedEffect(Unit) { model.reload() }
    DisposableEffect(Unit) { onDispose { model.clear() } }
    BackHandler(enabled = state.slug != null) { model.closeArticle() }
    if(state.slug != null) {
        val scroll = key(state.slug) { rememberScrollState() }
        Column(modifier.verticalScroll(scroll).padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            TextButton(onClick = model::closeArticle) { Text("Back to Learn") }
            if(state.articleBusy) { CircularProgressIndicator(); Text("Loading article…") }
            state.articleError?.let { Text(it, color = MaterialTheme.colorScheme.error); Button(onClick = { model.open(state.slug!!) }) { Text("Retry article") } }
            state.article?.let { article ->
                Text(article.title, style = MaterialTheme.typography.headlineLarge)
                Text(article.summary, style = MaterialTheme.typography.titleMedium)
                Text("Updated ${article.updatedAt.take(10)}", style = MaterialTheme.typography.labelSmall)
                article.content?.split("\n\n")?.forEach { Text(it, style = MaterialTheme.typography.bodyLarge) }
                Text("Educational information for exploration.", style = MaterialTheme.typography.bodySmall)
            }
        }
        return
    }
    Column(modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Build your market vocabulary", style = MaterialTheme.typography.headlineSmall)
        Text("Clear explanations for the terms used throughout YUDY.",
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        LazyColumn(Modifier.weight(1f), state = listState, verticalArrangement = Arrangement.spacedBy(12.dp), contentPadding = PaddingValues(bottom = 20.dp)) {
            if(state.busy) item { CircularProgressIndicator() }
            state.error?.let { message -> item { Text(message, color = MaterialTheme.colorScheme.error); Button(onClick = model::reload) { Text("Retry Learn") } } }
            if(!state.busy && state.error == null && state.articles.isEmpty()) item { Text("No articles available yet.") }
            items(state.articles, key = { it.slug }) { article ->
                Card(onClick = { model.open(article.slug) }, modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = YudyColors.Surface),
                    border = BorderStroke(1.dp, YudyColors.Line)) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(article.title, style = MaterialTheme.typography.titleLarge)
                        Text(article.summary, style = MaterialTheme.typography.bodyMedium)
                        Text("READ ARTICLE", style = MaterialTheme.typography.labelSmall, color = YudyColors.Cyan)
                    }
                }
            }
        }
    }
}
