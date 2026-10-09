package app.yudy

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.SystemBarStyle
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import app.yudy.ui.theme.YudyColors
import app.yudy.ui.theme.YudyTheme
import app.yudy.ui.auth.AuthNavigation
import app.yudy.ui.auth.AuthViewModel
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

data class LandingUiState(
    val title: String = "Meet the market\non your terms.",
    val description: String = "Explore real tokenized stocks, understand what sits underneath, and follow the themes that matter to you.",
)

class LandingViewModel : ViewModel() {
    private val mutableState = MutableStateFlow(LandingUiState())
    val state: StateFlow<LandingUiState> = mutableState.asStateFlow()
}

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge(statusBarStyle = SystemBarStyle.dark(android.graphics.Color.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.dark(android.graphics.Color.TRANSPARENT))
        setContent {
            YudyTheme {
                val authModel: AuthViewModel = viewModel()
                AuthNavigation(authModel) { openRegister, openLogin ->
                val model: LandingViewModel = viewModel()
                val state by model.state.collectAsStateWithLifecycle()
                Surface(modifier = Modifier.fillMaxSize()) {
                    Column(
                        Modifier.fillMaxSize()
                            .background(Brush.verticalGradient(listOf(
                                YudyColors.Surface, YudyColors.Midnight, YudyColors.Midnight,
                            )))
                            .safeDrawingPadding()
                            .verticalScroll(rememberScrollState())
                            .padding(horizontal = 22.dp, vertical = 20.dp),
                        verticalArrangement = Arrangement.spacedBy(20.dp),
                        horizontalAlignment = Alignment.Start,
                    ) {
                        Text(state.title, style = MaterialTheme.typography.displaySmall,
                            textAlign = TextAlign.Start)
                        Text(state.description, style = MaterialTheme.typography.bodyMedium,
                            color = YudyColors.Muted, textAlign = TextAlign.Start)
                        Box(Modifier.fillMaxWidth().height(212.dp)
                            .border(1.dp, YudyColors.Line, RoundedCornerShape(16.dp))
                            .background(Brush.verticalGradient(listOf(
                                YudyColors.Surface, YudyColors.Midnight, YudyColors.CyanDeep,
                            )), RoundedCornerShape(16.dp))) {
                            Box(Modifier.fillMaxWidth().height(86.dp).align(Alignment.BottomCenter)
                                .background(Brush.verticalGradient(listOf(
                                    Color.Transparent, YudyColors.Cyan.copy(alpha = 0.42f),
                                )), RoundedCornerShape(bottomStart = 16.dp, bottomEnd = 16.dp)))
                            Column(Modifier.fillMaxSize().padding(20.dp),
                                verticalArrangement = Arrangement.SpaceBetween) {
                                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                                    Row(verticalAlignment = Alignment.CenterVertically,
                                        horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                                        Image(painter = painterResource(R.drawable.yudy_mark),
                                            contentDescription = null, modifier = Modifier.size(38.dp))
                                        Text("YUDY", style = MaterialTheme.typography.titleLarge,
                                            fontWeight = FontWeight.Bold, letterSpacing = 1.8.sp)
                                    }
                                    Text("Explore what's next.", style = MaterialTheme.typography.headlineMedium)
                                }
                                Text("xSTOCKS\nGLOBAL MARKET", style = MaterialTheme.typography.labelSmall,
                                    color = YudyColors.White, lineHeight = 17.sp)
                            }
                        }
                        Column(Modifier.fillMaxWidth()
                            .border(1.dp, YudyColors.Line, RoundedCornerShape(12.dp))
                            .padding(horizontal = 16.dp)) {
                            listOf(
                                "01" to ("RISK PROFILE" to "Create your risk profile"),
                                "02" to ("XSTOCKS SELECTION" to "Get your list of xStocks"),
                                "03" to ("LIKE & SAVE" to "Like and save what interests you"),
                            ).forEachIndexed { index, (number, content) ->
                                Row(Modifier.fillMaxWidth().padding(vertical = 13.dp),
                                    verticalAlignment = Alignment.CenterVertically) {
                                    Text(number, Modifier.width(42.dp), style = MaterialTheme.typography.labelSmall,
                                        color = YudyColors.Cyan)
                                    Column {
                                        Text(content.first, style = MaterialTheme.typography.labelSmall,
                                            color = YudyColors.Muted, letterSpacing = 0.8.sp)
                                        Text(content.second, style = MaterialTheme.typography.bodySmall)
                                    }
                                }
                                if (index < 2) HorizontalDivider(color = YudyColors.Line)
                            }
                        }
                        Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Button(onClick = openRegister, modifier = Modifier.fillMaxWidth()) { Text("Create account") }
                            OutlinedButton(onClick = openLogin, modifier = Modifier.fillMaxWidth()) { Text("Sign in") }
                        }
                    }
                }
                }
            }
        }
    }
}
