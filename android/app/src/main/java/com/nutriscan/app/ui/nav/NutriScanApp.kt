package com.nutriscan.app.ui.nav

import androidx.compose.animation.AnimatedContentScope
import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.activity.ComponentActivity
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavBackStackEntry
import androidx.navigation.NavGraphBuilder
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.nutriscan.app.di.AppContainer
import com.nutriscan.app.ui.MainViewModel
import com.nutriscan.app.ui.ScanUiState
import com.nutriscan.app.ui.screens.AchievementsScreen
import com.nutriscan.app.ui.screens.AlertsScreen
import com.nutriscan.app.ui.screens.AskScreen
import com.nutriscan.app.ui.screens.ChatScreen
import com.nutriscan.app.ui.screens.ChatThreadsScreen
import com.nutriscan.app.ui.screens.DisputeScreen
import com.nutriscan.app.ui.screens.AnalyzingScreen
import com.nutriscan.app.ui.screens.HealthAnalysisScreen
import com.nutriscan.app.ui.screens.HistoryScreen
import com.nutriscan.app.ui.screens.HomeScreen
import com.nutriscan.app.ui.screens.InsightsScreen
import com.nutriscan.app.ui.screens.LoginScreen
import com.nutriscan.app.ui.screens.NutritionEntryScreen
import com.nutriscan.app.ui.screens.OnboardingScreen
import com.nutriscan.app.ui.screens.PhotoCaptureScreen
import com.nutriscan.app.ui.screens.ProInsightsScreen
import com.nutriscan.app.ui.screens.ReportsScreen
import com.nutriscan.app.ui.screens.SubmitReportScreen
import com.nutriscan.app.ui.screens.ProductDetailScreen
import com.nutriscan.app.ui.screens.ProfileScreen
import com.nutriscan.app.ui.screens.ScannerScreen
import com.nutriscan.app.ui.screens.SettingsScreen
import com.nutriscan.app.ui.screens.SplashScreen
import com.nutriscan.app.ui.screens.SubmitProductScreen
import com.nutriscan.app.ui.screens.SubscriptionScreen
import com.nutriscan.app.ui.theme.NutriScanTheme

private fun forwardEnter(): EnterTransition =
    slideInHorizontally(animationSpec = tween(320)) { it / 4 } + fadeIn(tween(320))

private fun forwardExit(): ExitTransition =
    slideOutHorizontally(animationSpec = tween(320)) { -it / 4 } + fadeOut(tween(320))

private fun backEnter(): EnterTransition =
    slideInHorizontally(animationSpec = tween(320)) { -it / 4 } + fadeIn(tween(320))

private fun backExit(): ExitTransition =
    slideOutHorizontally(animationSpec = tween(320)) { it / 4 } + fadeOut(tween(320))

private fun NavGraphBuilder.animatedComposable(
    route: String,
    content: @Composable AnimatedContentScope.(NavBackStackEntry) -> Unit,
) {
    composable(
        route = route,
        enterTransition = { forwardEnter() },
        exitTransition = { forwardExit() },
        popEnterTransition = { backEnter() },
        popExitTransition = { backExit() },
        content = content,
    )
}

@Composable
fun NutriScanApp() {
    val context = LocalContext.current
    val repository = remember(context) { AppContainer.repository(context) }
    val preferences = remember(context) { AppContainer.appPreferences(context) }
    val mainViewModel: MainViewModel = viewModel(factory = MainViewModel.Factory(repository))
    val navController = rememberNavController()
    var selectedGoal by remember { mutableStateOf("general_health") }

    val isLoggedIn by repository.isLoggedIn.collectAsState(initial = null)
    val darkModeOverride by preferences.darkModeOverride.collectAsState(initial = null)
    val useDarkTheme = darkModeOverride ?: isSystemInDarkTheme()

    // enableEdgeToEdge() in MainActivity only reads the theme once at cold start;
    // the in-app dark-mode override can diverge from the system setting afterwards,
    // so status/nav bar icon contrast has to be kept in sync here instead.
    val view = LocalView.current
    SideEffect {
        val window = (context as ComponentActivity).window
        val insetsController = WindowCompat.getInsetsController(window, view)
        insetsController.isAppearanceLightStatusBars = !useDarkTheme
        insetsController.isAppearanceLightNavigationBars = !useDarkTheme
    }

    // If a refresh fails (refresh token itself expired/revoked), TokenAuthenticator
    // clears the session; bounce straight to Login instead of leaving the user
    // stuck looking at raw 401 errors on whatever screen they were on.
    LaunchedEffect(isLoggedIn) {
        val currentRoute = navController.currentBackStackEntry?.destination?.route
        val exemptRoutes = setOf(Destination.Splash.route, Destination.Onboarding.route, Destination.Login.route)
        if (isLoggedIn == false && currentRoute !in exemptRoutes) {
            navController.navigate(Destination.Login.route) {
                popUpTo(0) { inclusive = true }
            }
        }
    }

    NutriScanTheme(useDarkTheme = useDarkTheme) {
        Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        NavHost(navController = navController, startDestination = Destination.Splash.route) {
            composable(Destination.Splash.route) {
                SplashScreen(
                    onFinished = {
                        val destination = if (isLoggedIn == true) Destination.Home.route else Destination.Onboarding.route
                        navController.navigate(destination) {
                            popUpTo(Destination.Splash.route) { inclusive = true }
                        }
                    },
                )
            }
            animatedComposable(Destination.Onboarding.route) {
                OnboardingScreen(
                    onContinue = { goal ->
                        selectedGoal = goal
                        navController.navigate(Destination.Login.route)
                    },
                )
            }
            animatedComposable(Destination.Login.route) {
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
            animatedComposable(Destination.Home.route) {
                HomeScreen(
                    repository = repository,
                    onScan = {
                        mainViewModel.resetScanState()
                        navController.navigate(Destination.Scanner.route)
                    },
                    onOpenHistory = { navController.navigate(Destination.History.route) },
                    onOpenProfile = { navController.navigate(Destination.Profile.route) },
                    onOpenSubscription = { navController.navigate(Destination.Subscription.route) },
                    onOpenSettings = { navController.navigate(Destination.Settings.route) },
                    onOpenInsights = { navController.navigate(Destination.Insights.route) },
                    onOpenAchievements = { navController.navigate(Destination.Achievements.route) },
                    onOpenAlerts = { navController.navigate(Destination.Alerts.route) },
                    onOpenAssistant = { navController.navigate(Destination.Chat.build()) },
                )
            }
            animatedComposable(Destination.Scanner.route) {
                ScannerScreen(
                    viewModel = mainViewModel,
                    onBack = { navController.popBackStack() },
                    onBarcodeCaptured = { navController.navigate(Destination.Analyzing.route) },
                    onTakePhotos = { navController.navigate(Destination.Capture.build(null)) },
                )
            }
            animatedComposable(Destination.Analyzing.route) {
                AnalyzingScreen(
                    viewModel = mainViewModel,
                    onSuccess = { barcode ->
                        navController.navigate(Destination.ProductDetail.build(barcode)) {
                            popUpTo(Destination.Home.route)
                        }
                    },
                    // Not in our database: straight to the photo screen, not a dead end.
                    onNeedsPhotos = { barcode ->
                        navController.navigate(Destination.Capture.build(barcode)) {
                            popUpTo(Destination.Analyzing.route) { inclusive = true }
                        }
                    },
                    // A failed attempt reopens the photo screen with the earlier photos kept.
                    onRetakePhotos = { barcode ->
                        val completing = mainViewModel.completingBarcode
                        val target = if (completing != null) Destination.CaptureNutrition.build(completing) else Destination.Capture.build(barcode)
                        navController.navigate(target) {
                            popUpTo(Destination.Analyzing.route) { inclusive = true }
                        }
                    },
                    onManualEntry = { barcode ->
                        val completing = mainViewModel.completingBarcode
                        val target = if (completing != null) Destination.NutritionEntry.build(completing) else Destination.SubmitProduct.build(barcode)
                        navController.navigate(target) {
                            popUpTo(if (completing != null) Destination.Analyzing.route else Destination.Home.route) {
                                inclusive = completing != null
                            }
                        }
                    },
                    onRetry = { navController.popBackStack(Destination.Scanner.route, inclusive = false) },
                )
            }
            animatedComposable(Destination.Capture.route) { backStackEntry ->
                val barcode = backStackEntry.arguments?.getString("barcode")?.takeIf { it != "none" }
                PhotoCaptureScreen(
                    viewModel = mainViewModel,
                    barcode = barcode,
                    onBack = { navController.popBackStack() },
                    onSubmit = {
                        navController.navigate(Destination.Analyzing.route) {
                            popUpTo(Destination.Capture.route) { inclusive = true }
                        }
                    },
                )
            }
            animatedComposable(Destination.CaptureNutrition.route) { backStackEntry ->
                val barcode = backStackEntry.arguments?.getString("barcode").orEmpty()
                PhotoCaptureScreen(
                    viewModel = mainViewModel,
                    barcode = barcode,
                    completeMode = true,
                    onBack = { navController.popBackStack() },
                    onSubmit = {
                        navController.navigate(Destination.Analyzing.route) {
                            popUpTo(Destination.CaptureNutrition.route) { inclusive = true }
                        }
                    },
                )
            }
            animatedComposable(Destination.NutritionEntry.route) { backStackEntry ->
                val barcode = backStackEntry.arguments?.getString("barcode").orEmpty()
                NutritionEntryScreen(
                    viewModel = mainViewModel,
                    barcode = barcode,
                    onBack = { navController.popBackStack() },
                    onSubmit = {
                        navController.navigate(Destination.Analyzing.route) {
                            popUpTo(Destination.NutritionEntry.route) { inclusive = true }
                        }
                    },
                )
            }
            animatedComposable(Destination.ProductDetail.route) {
                ProductDetailScreen(
                    viewModel = mainViewModel,
                    repository = repository,
                    preferences = preferences,
                    onBack = { navController.popBackStack() },
                    onAsk = { barcode -> navController.navigate(Destination.Ask.build(barcode)) },
                    onPhotographTable = { barcode -> navController.navigate(Destination.CaptureNutrition.build(barcode)) },
                    onTypeValues = { barcode -> navController.navigate(Destination.NutritionEntry.build(barcode)) },
                    onOpenReports = { barcode -> navController.navigate(Destination.Reports.build(barcode)) },
                    onViewAnalysis = {
                        val currentState = mainViewModel.scanState.value
                        val barcode = (currentState as? ScanUiState.Success)?.result?.product?.barcode.orEmpty()
                        navController.navigate(Destination.HealthAnalysis.build(barcode))
                    },
                )
            }
            animatedComposable(Destination.HealthAnalysis.route) {
                HealthAnalysisScreen(
                    viewModel = mainViewModel,
                    onBack = { navController.popBackStack(Destination.Home.route, inclusive = false) },
                )
            }
            animatedComposable(Destination.SubmitProduct.route) { backStackEntry ->
                val barcode = backStackEntry.arguments?.getString("barcode").orEmpty()
                SubmitProductScreen(
                    repository = repository,
                    barcode = barcode,
                    onBack = { navController.popBackStack(Destination.Home.route, inclusive = false) },
                    onSubmitted = { navController.popBackStack(Destination.Home.route, inclusive = false) },
                )
            }
            animatedComposable(Destination.Reports.route) { backStackEntry ->
                val barcode = backStackEntry.arguments?.getString("barcode").orEmpty()
                ReportsScreen(
                    repository = repository,
                    barcode = barcode,
                    onBack = { navController.popBackStack() },
                    onAddReport = { navController.navigate(Destination.SubmitReport.build(barcode)) },
                    onDispute = { navController.navigate(Destination.Dispute.build(barcode)) },
                )
            }
            animatedComposable(Destination.Chat.route) { backStackEntry ->
                val threadId = backStackEntry.arguments?.getString("threadId")?.toIntOrNull()
                ChatScreen(
                    repository = repository,
                    preferences = preferences,
                    threadId = threadId,
                    onBack = { navController.popBackStack() },
                    onOpenThreads = { navController.navigate(Destination.ChatThreads.route) },
                )
            }
            animatedComposable(Destination.ChatThreads.route) {
                ChatThreadsScreen(
                    repository = repository,
                    onBack = { navController.popBackStack() },
                    onOpen = { threadId ->
                        // Replace the current chat with the chosen one instead of stacking chats.
                        navController.navigate(Destination.Chat.build(threadId)) {
                            popUpTo(Destination.Home.route)
                        }
                    },
                )
            }
            animatedComposable(Destination.Ask.route) { backStackEntry ->
                val barcode = backStackEntry.arguments?.getString("barcode").orEmpty()
                AskScreen(
                    viewModel = mainViewModel,
                    repository = repository,
                    preferences = preferences,
                    barcode = barcode,
                    onBack = { navController.popBackStack() },
                )
            }
            animatedComposable(Destination.Alerts.route) {
                AlertsScreen(
                    repository = repository,
                    onBack = { navController.popBackStack() },
                    onOpenProduct = { barcode -> navController.navigate(Destination.Reports.build(barcode)) },
                )
            }
            animatedComposable(Destination.Dispute.route) { backStackEntry ->
                val barcode = backStackEntry.arguments?.getString("barcode").orEmpty()
                DisputeScreen(
                    repository = repository,
                    barcode = barcode,
                    onBack = { navController.popBackStack() },
                    onSubmitted = { navController.popBackStack() },
                )
            }
            animatedComposable(Destination.SubmitReport.route) { backStackEntry ->
                val barcode = backStackEntry.arguments?.getString("barcode").orEmpty()
                SubmitReportScreen(
                    repository = repository,
                    barcode = barcode,
                    onBack = { navController.popBackStack() },
                    onSubmitted = { navController.popBackStack() },
                )
            }
            animatedComposable(Destination.ProInsights.route) {
                ProInsightsScreen(repository = repository, onBack = { navController.popBackStack() })
            }
            animatedComposable(Destination.History.route) {
                HistoryScreen(
                    repository = repository,
                    onBack = { navController.popBackStack() },
                    onOpenScan = { item ->
                        mainViewModel.openScan(item)
                        navController.navigate(Destination.ProductDetail.build(item.product.barcode))
                    },
                )
            }
            animatedComposable(Destination.Profile.route) {
                ProfileScreen(repository = repository, onBack = { navController.popBackStack() })
            }
            animatedComposable(Destination.Subscription.route) {
                SubscriptionScreen(repository = repository, onBack = { navController.popBackStack() })
            }
            animatedComposable(Destination.Settings.route) {
                SettingsScreen(
                    repository = repository,
                    preferences = preferences,
                    onBack = { navController.popBackStack() },
                    onLoggedOut = {
                        navController.navigate(Destination.Onboarding.route) {
                            popUpTo(0) { inclusive = true }
                        }
                    },
                )
            }
            animatedComposable(Destination.Achievements.route) {
                AchievementsScreen(repository = repository, onBack = { navController.popBackStack() })
            }
            animatedComposable(Destination.Insights.route) {
                InsightsScreen(repository = repository, onBack = { navController.popBackStack() })
            }
        }
        }
    }
}
