package com.tlex.tv.ui.navigation

sealed class Screen(val route: String) {
    object Setup : Screen("setup")
    object WebView : Screen("webview")
}
