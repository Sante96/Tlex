package com.tlex.tv.ui.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.tlex.tv.ui.screens.setup.ServerSetupScreen
import com.tlex.tv.ui.screens.webview.TvWebView

@Composable
fun TlexNavGraph(
    modifier: Modifier = Modifier
) {
    val viewModel: NavViewModel = hiltViewModel()
    val navController = rememberNavController()
    val serverUrl by viewModel.preferences.serverUrl.collectAsState(initial = null)
    val url = serverUrl ?: return

    val startDestination = if (url.isBlank()) Screen.Setup.route else Screen.WebView.route

    NavHost(
        navController = navController,
        startDestination = startDestination,
        modifier = modifier
    ) {
        composable(Screen.Setup.route) {
            ServerSetupScreen(
                onSetupComplete = {
                    navController.navigate(Screen.WebView.route) {
                        popUpTo(Screen.Setup.route) { inclusive = true }
                    }
                }
            )
        }

        composable(Screen.WebView.route) {
            TvWebView(serverUrl = url)
        }
    }
}
