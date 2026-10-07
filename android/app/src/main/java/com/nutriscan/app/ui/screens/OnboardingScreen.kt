package com.nutriscan.app.ui.screens

import androidx.compose.animation.core.animateDpAsState
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.Insights
import androidx.compose.material.icons.rounded.MonitorHeart
import androidx.compose.material.icons.rounded.QrCodeScanner
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.nutriscan.app.ui.components.AnimatedGradientBackground
import com.nutriscan.app.ui.components.NsButton
import com.nutriscan.app.ui.theme.NsCream
import com.nutriscan.app.ui.theme.NsEmerald900
import com.nutriscan.app.ui.theme.NsGold300
import kotlinx.coroutines.launch

private data class OnboardingPage(
    val icon: ImageVector,
    val title: String,
    val description: String,
)

private val pages = listOf(
    OnboardingPage(
        Icons.Rounded.QrCodeScanner,
        "Scan any packaged food",
        "Point your camera at a barcode and get instant nutrition data — no typing, no guessing.",
    ),
    OnboardingPage(
        Icons.Rounded.Insights,
        "WHO-based health scoring",
        "Every product is scored 1–10 against WHO sugar, sodium and fat thresholds — not marketing claims.",
    ),
    OnboardingPage(
        Icons.Rounded.MonitorHeart,
        "Built for diabetic care",
        "Get a clear Safe / Moderate / Avoid read on refined carbs and sugar — before you buy, not after.",
    ),
)

private val goals = listOf(
    "general_health" to "General health",
    "diabetes" to "Diabetes management",
    "weight_loss" to "Weight loss",
    "hypertension" to "Hypertension management",
)

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun OnboardingScreen(onContinue: (goal: String) -> Unit) {
    val pagerState = rememberPagerState(pageCount = { pages.size + 1 })
    val scope = rememberCoroutineScope()
    var selectedGoal by remember { mutableStateOf(goals.first().first) }

    AnimatedGradientBackground(colors = listOf(NsEmerald900, Color(0xFF123D2C), NsEmerald900)) {
        Column(modifier = Modifier.fillMaxSize()) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(20.dp),
                horizontalArrangement = Arrangement.End,
            ) {
                if (pagerState.currentPage < pages.size) {
                    TextButton(onClick = { scope.launch { pagerState.animateScrollToPage(pages.size) } }) {
                        Text("Skip", color = NsCream)
                    }
                }
            }

            HorizontalPager(
                state = pagerState,
                modifier = Modifier.weight(1f).fillMaxWidth(),
            ) { page ->
                val pageOffset = (pagerState.currentPage - page) + pagerState.currentPageOffsetFraction
                if (page < pages.size) {
                    OnboardingPageContent(pages[page], pageOffset)
                } else {
                    GoalSelectionContent(selectedGoal, pageOffset) { selectedGoal = it }
                }
            }

            Row(
                modifier = Modifier.fillMaxWidth().padding(vertical = 16.dp),
                horizontalArrangement = Arrangement.Center,
            ) {
                repeat(pages.size + 1) { index ->
                    val isActive = pagerState.currentPage == index
                    val dotWidth by animateDpAsState(if (isActive) 24.dp else 8.dp, label = "dotWidth")
                    Box(
                        modifier = Modifier
                            .padding(horizontal = 4.dp)
                            .height(8.dp)
                            .width(dotWidth)
                            .background(
                                if (isActive) NsGold300 else NsCream.copy(alpha = 0.35f),
                                CircleShape,
                            ),
                    )
                }
            }

            Box(modifier = Modifier.fillMaxWidth().padding(horizontal = 24.dp, vertical = 8.dp)) {
                NsButton(
                    text = if (pagerState.currentPage == pages.size) "Get started" else "Next",
                    onClick = {
                        if (pagerState.currentPage == pages.size) {
                            onContinue(selectedGoal)
                        } else {
                            scope.launch { pagerState.animateScrollToPage(pagerState.currentPage + 1) }
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
            Spacer(Modifier.height(12.dp))
        }
    }
}

@Composable
private fun OnboardingPageContent(page: OnboardingPage, pageOffset: Float) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 32.dp)
            .parallax(pageOffset),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Box(
            modifier = Modifier
                .size(120.dp)
                .background(Color.White.copy(alpha = 0.08f), CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Icon(page.icon, contentDescription = null, tint = NsGold300, modifier = Modifier.size(56.dp))
        }
        Spacer(Modifier.height(32.dp))
        Text(page.title, style = MaterialTheme.typography.headlineSmall, color = NsCream, textAlign = TextAlign.Center)
        Spacer(Modifier.height(12.dp))
        Text(
            page.description,
            style = MaterialTheme.typography.bodyLarge,
            color = NsCream.copy(alpha = 0.75f),
            textAlign = TextAlign.Center,
        )
    }
}

@Composable
private fun GoalSelectionContent(selectedGoal: String, pageOffset: Float, onSelect: (String) -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 32.dp)
            .parallax(pageOffset),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text(
            "What's your main goal?",
            style = MaterialTheme.typography.headlineSmall,
            color = NsCream,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(24.dp))
        goals.forEach { (key, label) ->
            val isSelected = selectedGoal == key
            Card(
                onClick = { onSelect(key) },
                modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp),
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(
                    containerColor = if (isSelected) NsGold300.copy(alpha = 0.18f) else Color.White.copy(alpha = 0.06f),
                ),
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth().padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Text(label, color = NsCream, style = MaterialTheme.typography.titleMedium)
                    if (isSelected) {
                        Icon(Icons.Rounded.Check, contentDescription = null, tint = NsGold300)
                    }
                }
            }
        }
    }
}

private fun Modifier.parallax(pageOffset: Float): Modifier = this.graphicsLayer {
    val clamped = pageOffset.coerceIn(-1f, 1f)
    alpha = 1f - kotlin.math.abs(clamped)
    val scale = 1f - (kotlin.math.abs(clamped) * 0.15f)
    scaleX = scale
    scaleY = scale
    translationX = clamped * size.width * 0.3f
}
