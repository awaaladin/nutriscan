package com.nutriscan.app.ui.nav

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.nutriscan.app.di.AppContainer
import com.nutriscan.app.ui.MainViewModel
import com.nutriscan.app.ui.ScanUiState
import com.nutriscan.app.ui.screens.HealthAnalysisScreen
import com.nutriscan.app.ui.screens.HistoryScreen
import com.nutriscan.app.ui.screens.HomeScreen
import com.nutriscan.app.ui.screens.LoginScreen
import com.nutriscan.app.ui.screens.OnboardingScreen
import com.nutriscan.app.ui.screens.ProInsightsScreen
import com.nutriscan.app.ui.screens.ProductDetailScreen
import com.nutriscan.app.ui.screens.ProfileScreen
import com.nutriscan.app.ui.screens.ScannerScreen
import com.nutriscan.app.ui.screens.SubmitProductScreen
import com.nutriscan.app.ui.screens.SubscriptionScreen

@Composable
fun NutriScanApp() {
    val context = LocalContext.current
    val repository = remember(context) { AppContainer.repository(context) }
    val mainViewModel: MainViewModel = viewModel(factory = MainViewModel.Factory(repository))
    val navController = rememberNavController()
    var selectedGoal by remember { mutableStateOf("general_health") }

    val isLoggedIn by repository.isLoggedIn.collectAsState(initial = null)

    when (isLoggedIn) {
        null -> Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            CircularProgressIndicator()
        }
        else -> NavHost(
            navController = navController,
            startDestination = if (isLoggedIn == true) Destination.Home.route else Destination.Onboarding.route,
        ) {
            composable(Destination.Onboarding.route) {
                OnboardingScreen(
                    onContinue = { goal ->
                        selectedGoal = goal
                        navController.navigate(Destination.Login.route)
                    },
                )
            }
            composable(Destination.Login.route) {
                LoginScreen(
                    repository = repository,
                    defaultGoal = selectedGoal,
                    onAuthenticated = {
                        navController.navigate(Destination.Home.route) {
                            popUpTo(Destination.Onboarding.route) { inclusive = true }
                        }
                    },
                )
            }
            composable(Destination.Home.route) {
                HomeScreen(
                    repository = repository,
                    onScan = {
                        mainViewModel.resetScanState()
                        navController.navigate(Destination.Scanner.route)
                    },
                    onOpenHistory = { navController.navigate(Destination.History.route) },
                    onOpenProfile = { navController.navigate(Destination.Profile.route) },
                    onOpenSubscription = { navController.navigate(Destination.Subscription.route) },
                )
            }
            composable(Destination.Scanner.route) {
                ScannerScreen(
                    viewModel = mainViewModel,
                    onProductFound = { barcode -> navController.navigate(Destination.ProductDetail.build(barcode)) },
                    onNotFound = { barcode -> navController.navigate(Destination.SubmitProduct.build(barcode)) },
                )
            }
            composable(Destination.ProductDetail.route) {
                ProductDetailScreen(
                    viewModel = mainViewModel,
                    onViewAnalysis = {
                        val currentState = mainViewModel.scanState.value
                        val barcode = (currentState as? ScanUiState.Success)?.result?.product?.barcode.orEmpty()
                        navController.navigate(Destination.HealthAnalysis.build(barcode))
                    },
                )
            }
            composable(Destination.HealthAnalysis.route) {
                HealthAnalysisScreen(
                    viewModel = mainViewModel,
                    onBack = {
                        navController.popBackStack(Destination.Home.route, inclusive = false)
                    },
                )
            }
            composable(Destination.SubmitProduct.route) { backStackEntry ->
                val barcode = backStackEntry.arguments?.getString("barcode").orEmpty()
                SubmitProductScreen(
                    repository = repository,
                    barcode = barcode,
                    onSubmitted = { navController.popBackStack(Destination.Home.route, inclusive = false) },
                )
            }
            composable(Destination.ProInsights.route) {
                ProInsightsScreen(repository = repository)
            }
            composable(Destination.History.route) {
                HistoryScreen(repository = repository)
            }
            composable(Destination.Profile.route) {
                ProfileScreen(repository = repository)
            }
            composable(Destination.Subscription.route) {
                SubscriptionScreen(repository = repository)
            }
        }
    }
}
