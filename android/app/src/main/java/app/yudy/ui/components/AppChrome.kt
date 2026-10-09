package app.yudy.ui.components

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.Logout
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import app.yudy.R
import app.yudy.domain.auth.AuthUser
import app.yudy.ui.auth.AuthViewModel
import app.yudy.ui.theme.YudyColors

enum class AppSection(val title: String, val label: String, val icon: ImageVector) {
    FOR_YOU("For You", "For You", Icons.Outlined.AutoAwesome),
    DISCOVER("Discover", "Discover", Icons.Outlined.Search),
    SAVED("Saved", "Saved", Icons.Outlined.BookmarkBorder),
    LEARN("Learn", "Learn", Icons.Outlined.School),
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun YudyAppScaffold(
    user: AuthUser,
    auth: AuthViewModel,
    section: AppSection,
    select: (AppSection) -> Unit,
    openSettings: () -> Unit,
    content: @Composable (PaddingValues) -> Unit,
) {
    var menuOpen by remember { mutableStateOf(false) }
    var confirmDelete by remember { mutableStateOf(false) }
    val authState by auth.state.collectAsStateWithLifecycle()
    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        Image(painterResource(R.drawable.yudy_mark), null, Modifier.size(30.dp))
                        Text("YUDY // ${section.title.uppercase()}",
                            style = MaterialTheme.typography.labelSmall,
                            color = YudyColors.Cyan, fontWeight = FontWeight.Bold,
                            fontSize = 17.sp, lineHeight = 22.sp, letterSpacing = 0.6.sp)
                    }
                },
                actions = {
                    IconButton(onClick = { menuOpen = true },
                        colors = IconButtonDefaults.iconButtonColors(
                            containerColor = YudyColors.White, contentColor = YudyColors.Midnight)) {
                        Icon(Icons.Outlined.Person, "Open profile and settings")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
            )
        },
        bottomBar = {
            Column {
                HorizontalDivider(color = YudyColors.Line)
                NavigationBar(containerColor = YudyColors.Midnight) {
                    AppSection.entries.forEach { item ->
                        NavigationBarItem(
                            selected = item == section,
                            onClick = { select(item) },
                            icon = { Icon(item.icon, null) },
                            label = { Text(item.label, maxLines = 1) },
                            colors = NavigationBarItemDefaults.colors(
                                selectedIconColor = YudyColors.Midnight,
                                selectedTextColor = YudyColors.White,
                                indicatorColor = YudyColors.White,
                                unselectedIconColor = YudyColors.Muted,
                                unselectedTextColor = YudyColors.Muted,
                            ),
                        )
                    }
                }
            }
        },
        content = content,
    )
    if (menuOpen) {
        ModalBottomSheet(onDismissRequest = { menuOpen = false }, containerColor = YudyColors.Surface) {
            Column(Modifier.fillMaxWidth().padding(horizontal = 24.dp).padding(bottom = 28.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Box(Modifier.size(54.dp).clip(CircleShape).background(YudyColors.White),
                    contentAlignment = Alignment.Center) {
                    Text(user.email.take(1).uppercase(), color = YudyColors.Midnight,
                        style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                }
                Text("Profile & settings", style = MaterialTheme.typography.headlineSmall)
                Text(user.email, style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1, overflow = TextOverflow.Ellipsis)
                HorizontalDivider(Modifier.padding(vertical = 8.dp))
                SettingsRow(Icons.Outlined.Tune, "Investor profile", "Risk profile and exploration preferences") {
                    menuOpen = false
                    openSettings()
                }
                SettingsRow(Icons.AutoMirrored.Outlined.Logout, "Sign out", "End this session") {
                    menuOpen = false
                    auth.logout()
                }
                SettingsRow(Icons.Outlined.DeleteOutline, "Delete account", "Permanently remove your account",
                    destructive = true) {
                    menuOpen = false
                    confirmDelete = true
                }
                authState.error?.let { Text(it, color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall) }
            }
        }
    }
    if (confirmDelete) {
        AlertDialog(
            onDismissRequest = { if (!authState.busy) confirmDelete = false },
            icon = { Icon(Icons.Outlined.DeleteForever, null, tint = MaterialTheme.colorScheme.error) },
            title = { Text("Delete your account?") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("Your profile, risk answers, saved assets and activity will be permanently removed. This cannot be undone.")
                    authState.error?.let {
                        Text(it, color = MaterialTheme.colorScheme.error,
                            style = MaterialTheme.typography.bodySmall)
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { auth.deleteAccount() }, enabled = !authState.busy) {
                    Text("Delete permanently", color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = { TextButton(onClick = { confirmDelete = false }, enabled = !authState.busy) { Text("Cancel") } },
        )
    }
}

@Composable
private fun SettingsRow(
    icon: ImageVector,
    title: String,
    description: String,
    destructive: Boolean = false,
    action: () -> Unit,
) {
    TextButton(onClick = action, modifier = Modifier.fillMaxWidth(),
        contentPadding = PaddingValues(horizontal = 4.dp, vertical = 10.dp)) {
        Icon(icon, null, tint = if (destructive) MaterialTheme.colorScheme.error else YudyColors.Muted)
        Spacer(Modifier.width(16.dp))
        Column(Modifier.weight(1f), horizontalAlignment = Alignment.Start) {
            Text(title, color = if (destructive) MaterialTheme.colorScheme.error else YudyColors.White,
                style = MaterialTheme.typography.titleSmall)
            Text(description, color = MaterialTheme.colorScheme.onSurfaceVariant,
                style = MaterialTheme.typography.bodySmall)
        }
        Icon(Icons.Outlined.ChevronRight, null, tint = YudyColors.Muted)
    }
}
