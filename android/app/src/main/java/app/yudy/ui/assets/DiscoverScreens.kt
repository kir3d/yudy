package app.yudy.ui.assets

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Search
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import app.yudy.domain.assets.*
import app.yudy.domain.auth.AuthUser
import app.yudy.ui.auth.AuthViewModel
import app.yudy.ui.components.AppSection
import app.yudy.ui.components.YudyAppScaffold
import app.yudy.ui.theme.YudyColors

@Composable
fun DiscoverFlow(user: AuthUser, auth: AuthViewModel, consent: () -> Unit, onProfile: () -> Unit) {
    var section by remember(user.id) { mutableStateOf(AppSection.FOR_YOU) }
    var selectedXStock by remember(user.id) { mutableStateOf<XStockSuggestion?>(null) }
    var buyXStock by remember(user.id) { mutableStateOf<XStockSuggestion?>(null) }
    val model: DiscoverViewModel = viewModel()
    val state by model.state.collectAsStateWithLifecycle()
    val listState = rememberLazyListState()
    LaunchedEffect(user.id) { model.bindUser(user.id) }
    DisposableEffect(user.id) { onDispose { model.clear() } }
    LaunchedEffect(state.consentRequired, state.sessionExpired) {
        if (state.consentRequired) consent()
        if (state.sessionExpired) auth.restore()
    }
    LaunchedEffect(state.search, state.assetType, state.sort) { listState.scrollToItem(0) }
    val keyboard = LocalSoftwareKeyboardController.current
    val focus = LocalFocusManager.current
    val submitSearch: () -> Unit = { focus.clearFocus(); keyboard?.hide(); model.search() }
    BackHandler(enabled = selectedXStock == null && buyXStock == null) { onProfile() }
    if (buyXStock != null) {
        XStockBuyScreen(buyXStock!!, back = { buyXStock = null }, consent = consent,
            restoreSession = auth::restore)
    } else if (selectedXStock != null) {
        XStockDetailScreen(selectedXStock!!, back = { selectedXStock = null })
    } else YudyAppScaffold(user, auth, section, {
        section = it
    }, onProfile) { insets ->
        when (section) {
            AppSection.FOR_YOU -> ForYouScreen(user, auth, consent, onProfile,
                openAsset = { selectedXStock = it },
                openBuy = { buyXStock = it },
                modifier = Modifier.fillMaxSize().padding(insets))
            AppSection.SAVED -> SavedScreen(user, auth, consent,
                openAsset = { selectedXStock = it }, openBuy = { buyXStock = it },
                modifier = Modifier.fillMaxSize().padding(insets))
            AppSection.LEARN -> app.yudy.ui.learn.LearnScreen(
                modifier = Modifier.fillMaxSize().padding(insets))
            AppSection.DISCOVER -> {
                Column(Modifier.fillMaxSize().padding(insets).imePadding().padding(horizontal = 20.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text("OFFICIAL xSTOCKS · LIVE MARKET DATA",
                        style = MaterialTheme.typography.labelSmall, color = YudyColors.Cyan,
                        modifier = Modifier.padding(top = 8.dp))
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        OutlinedTextField(state.searchText, model::searchText, label = { Text("Search symbol or name") },
                            singleLine = true, keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                            keyboardActions = KeyboardActions(onSearch = { submitSearch() }), modifier = Modifier.weight(1f))
                        IconButton(onClick = submitSearch) { Icon(Icons.Outlined.Search, "Search") }
                    }
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalAlignment = Alignment.CenterVertically) {
                        FilterChip(selected = state.assetType == null,
                            onClick = { model.apply(null, state.sort) }, label = { Text("All") })
                        FilterChip(selected = state.assetType == "STOCK",
                            onClick = { model.apply("STOCK", state.sort) }, label = { Text("Stocks") })
                        FilterChip(selected = state.assetType == "ETF",
                            onClick = { model.apply("ETF", state.sort) }, label = { Text("ETFs") })
                        Spacer(Modifier.weight(1f))
                        SortMenu(state.sort) { model.apply(state.assetType, it) }
                    }
                    Text("${state.total} real xStocks", style = MaterialTheme.typography.labelLarge,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                    LazyColumn(Modifier.weight(1f).fillMaxWidth(), state = listState,
                        verticalArrangement = Arrangement.spacedBy(10.dp), contentPadding = PaddingValues(bottom = 24.dp)) {
                        if (state.busy) item { CircularProgressIndicator(); Text("Loading the catalog…") }
                        state.error?.let { error -> item { Text(error, color = MaterialTheme.colorScheme.error); Button(onClick = model::reload) { Text("Retry") } } }
                        if (!state.busy && state.error == null && state.items.isEmpty()) item {
                            Text("No assets match these filters.", style = MaterialTheme.typography.titleMedium)
                            TextButton(onClick = model::resetFilters) { Text("Clear filters") }
                        }
                        state.actionError?.let { message -> item {
                            Text(message, color = MaterialTheme.colorScheme.error,
                                style = MaterialTheme.typography.bodySmall)
                        } }
                        items(state.items, key = { it.id }) { asset ->
                            XStockCard(asset, busy = asset.id in state.changing,
                                onAction = { model.change(asset, it) },
                                onBuy = { buyXStock = asset }) { selectedXStock = asset }
                        }
                        item {
                            state.pageError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                            if (state.loadingMore) CircularProgressIndicator()
                            else if (state.nextCursor != null) OutlinedButton(onClick = model::loadMore,
                                modifier = Modifier.fillMaxWidth()) { Text("Load more") }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun SortMenu(selected: String, choose: (String) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    Box {
        TextButton(onClick = { expanded = true }) {
            Text(when (selected) {
                "name" -> "Name"
                "price_asc" -> "Price ↑"
                "price_desc" -> "Price ↓"
                else -> "Symbol"
            })
        }
        DropdownMenu(expanded, onDismissRequest = { expanded = false }) {
            listOf("symbol" to "Symbol", "name" to "Name", "price_asc" to "Price: low to high",
                "price_desc" to "Price: high to low").forEach { (value, label) ->
                DropdownMenuItem(text = { Text(label) }, onClick = {
                    choose(value); expanded = false
                })
            }
        }
    }
}

@Composable
fun DemoBanner() {
    Surface(color = YudyColors.Surface, shape = MaterialTheme.shapes.medium,
        border = BorderStroke(1.dp, YudyColors.Line)) {
        Text("Demo data · fictional instruments and synthetic prices", Modifier.fillMaxWidth().padding(12.dp),
            style = MaterialTheme.typography.bodySmall, color = YudyColors.Muted)
    }
}

@Composable
fun AssetCard(asset: AssetSummary, open: () -> Unit) {
    Surface(onClick = open, modifier = Modifier.fillMaxWidth(), color = YudyColors.Surface,
        shape = RoundedCornerShape(12.dp), border = BorderStroke(1.dp, YudyColors.Line)) {
        Row(Modifier.padding(16.dp), horizontalArrangement = Arrangement.spacedBy(14.dp),
            verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(42.dp).clip(RoundedCornerShape(10.dp)).background(YudyColors.SurfaceVariant),
                contentAlignment = Alignment.Center) {
                Text(asset.symbol.take(2), style = MaterialTheme.typography.labelLarge, color = YudyColors.Cyan)
            }
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text(asset.symbol, style = MaterialTheme.typography.titleMedium)
                    Text(money(asset.price, asset.currency), style = MaterialTheme.typography.titleMedium)
                }
                Text(asset.name, style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1)
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text(listOfNotNull(asset.sector, if (asset.type == "ETF") "ETF" else "Stock")
                        .joinToString(" · "), style = MaterialTheme.typography.labelSmall,
                        color = YudyColors.Muted)
                    Text("${percent(asset.performance1y)} · 1Y",
                        style = MaterialTheme.typography.labelMedium,
                        color = if (asset.performance1y?.toBigDecimalOrNull()?.signum() == -1)
                            MaterialTheme.colorScheme.error else YudyColors.Cyan)
                }
            }
        }
    }
}

@Composable
private fun FilterDialog(filters: CatalogFilters, initial: CatalogQuery, dismiss: () -> Unit, apply: (CatalogQuery) -> Unit) {
    var draft by remember(initial) { mutableStateOf(initial) }
    AlertDialog(onDismissRequest = dismiss, title = { Text("Explore the full catalog") }, text = {
        Column(Modifier.heightIn(max = 480.dp).verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(8.dp)) {
            ChoiceDropdown("Region", filters.regions, draft.region) { draft = draft.copy(region = it) }
            ChoiceDropdown("Market", filters.markets, draft.market) { draft = draft.copy(market = it) }
            ChoiceDropdown("Sector", filters.sectors, draft.sector) { draft = draft.copy(sector = it) }
            ChoiceDropdown("Industry", filters.industries, draft.industry) { draft = draft.copy(industry = it) }
            ChoiceDropdown("Theme", filters.themes, draft.theme) { draft = draft.copy(theme = it) }
            ChoiceDropdown("Asset type", filters.assetTypes, draft.assetType) { draft = draft.copy(assetType = it) }
            ChoiceDropdown("Sort", listOf(FilterChoice("symbol", "Symbol"), FilterChoice("name", "Name"),
                FilterChoice("price_asc", "Price: low to high"), FilterChoice("price_desc", "Price: high to low")),
                draft.sort, includeAll = false) { draft = draft.copy(sort = it ?: "symbol") }
        }
    }, confirmButton = { TextButton(onClick = { apply(draft) }) { Text("Apply filters") } },
        dismissButton = { TextButton(onClick = dismiss) { Text("Cancel") } })
}

@Composable
private fun ChoiceDropdown(label: String, options: List<FilterChoice>, selected: String?, includeAll: Boolean = true,
    choose: (String?) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    Box {
        OutlinedButton(onClick = { expanded = true }, modifier = Modifier.fillMaxWidth()) {
            Text("$label: ${options.find { it.code == selected }?.title ?: "All"}")
        }
        DropdownMenu(expanded, onDismissRequest = { expanded = false }, modifier = Modifier.heightIn(max = 320.dp)) {
            if (includeAll) DropdownMenuItem(text = { Text("All") }, onClick = { choose(null); expanded = false })
            options.forEach { option -> DropdownMenuItem(text = { Text(option.title) },
                onClick = { choose(option.code); expanded = false }) }
        }
    }
}
