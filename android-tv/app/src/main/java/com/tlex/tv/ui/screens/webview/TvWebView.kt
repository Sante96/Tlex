@file:Suppress("RedundantSuppression")

package com.tlex.tv.ui.screens.webview

import android.annotation.SuppressLint
import android.app.Activity
import android.view.View
import android.view.ViewGroup
import android.webkit.CookieManager
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView

@SuppressLint("SetJavaScriptEnabled")
@Composable
@Suppress("UNUSED_PARAMETER")
fun TvWebView(
    serverUrl: String,
    /** The URL doesn't load the TLEX app: let the user fix it instead of being stuck */
    onServerUnreachable: () -> Unit
) {
    val context = LocalContext.current
    val targetUrl = remember(serverUrl) { "$serverUrl?platform=tv" }
    val currentOnServerUnreachable by rememberUpdatedState(onServerUnreachable)

    val webView = remember {
        WebView(context).apply {
            layoutParams = ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )

            // --- Keeps the screen on during video playback ---
            keepScreenOn = true

            // --- No overscroll bounce on TV (no touch, looks wrong with D-pad) ---
            overScrollMode = View.OVER_SCROLL_NEVER

            // --- Hide scrollbars: TV navigates via D-pad, no scroll indicator needed ---
            isScrollbarFadingEnabled = true
            scrollBarStyle = View.SCROLLBARS_INSIDE_OVERLAY

            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.mediaPlaybackRequiresUserGesture = false
            settings.allowFileAccess = false // the app is served over HTTP; no file:// access
            settings.useWideViewPort = true
            settings.loadWithOverviewMode = true

            // --- TV has no touch pinch-zoom; disable zoom UI entirely ---
            settings.setSupportZoom(false)
            settings.builtInZoomControls = false
            settings.displayZoomControls = false

            // --- Tell WebView the network is up; skips connectivity probing on load ---
            setNetworkAvailable(true)

            // --- Identify as TV client so the backend/frontend can adapt ---
            settings.userAgentString = "${settings.userAgentString} TlexTV/1.0"

            CookieManager.getInstance().setAcceptCookie(true)
            CookieManager.getInstance().setAcceptThirdPartyCookies(this, true)

            webViewClient = object : WebViewClient() {
                private var reported = false

                private fun reportUnreachable() {
                    if (!reported) {
                        reported = true
                        currentOnServerUnreachable()
                    }
                }

                override fun shouldOverrideUrlLoading(
                    view: WebView,
                    request: WebResourceRequest
                ): Boolean {
                    return !request.url.toString().startsWith(serverUrl)
                }

                override fun onReceivedError(
                    view: WebView,
                    request: WebResourceRequest,
                    error: WebResourceError
                ) {
                    if (request.isForMainFrame) reportUnreachable()
                }

                override fun onReceivedHttpError(
                    view: WebView,
                    request: WebResourceRequest,
                    errorResponse: WebResourceResponse
                ) {
                    // e.g. Cloudflare's "tunnel error" page (530) when TLEX isn't running
                    if (request.isForMainFrame && errorResponse.statusCode >= 500) reportUnreachable()
                }

                override fun onPageFinished(view: WebView, url: String) {
                    // The backend's port (8000) answers JSON, not the web app (3000)
                    view.evaluateJavascript("document.contentType") { type ->
                        if (type.contains("json")) reportUnreachable()
                    }
                }
            }

            // --- WebChromeClient: handles JS fullscreen API (requestFullscreen()) ---
            webChromeClient = object : WebChromeClient() {
                private var customView: View? = null
                private var customViewCallback: CustomViewCallback? = null

                override fun onShowCustomView(view: View, callback: CustomViewCallback) {
                    // A video called requestFullscreen() — show it over the WebView
                    customView = view
                    customViewCallback = callback
                    (this@apply.parent as? ViewGroup)?.addView(
                        view,
                        ViewGroup.LayoutParams(
                            ViewGroup.LayoutParams.MATCH_PARENT,
                            ViewGroup.LayoutParams.MATCH_PARENT
                        )
                    )
                    this@apply.visibility = View.GONE
                }

                override fun onHideCustomView() {
                    (customView?.parent as? ViewGroup)?.removeView(customView)
                    customView = null
                    customViewCallback?.onCustomViewHidden()
                    customViewCallback = null
                    this@apply.visibility = View.VISIBLE
                }
            }

            loadUrl(targetUrl)
        }
    }

    // Always enabled: `enabled = webView.canGoBack()` was only evaluated at composition
    // (WebView navigation doesn't recompose), so Back always left the app
    BackHandler {
        if (webView.canGoBack()) webView.goBack() else (context as? Activity)?.finish()
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black)
    ) {
        AndroidView(
            factory = { webView },
            modifier = Modifier.fillMaxSize()
        )
    }
}
