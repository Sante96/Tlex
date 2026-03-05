package com.tlex.tv.ui.screens.setup

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import com.tlex.tv.ui.theme.BackgroundPrimary
import com.tlex.tv.ui.theme.BackgroundSecondary
import com.tlex.tv.ui.theme.SurfaceVariant
import com.tlex.tv.ui.theme.TextPrimary
import com.tlex.tv.ui.theme.TextSecondary
import com.tlex.tv.ui.theme.TlexGold

@Composable
fun ServerSetupScreen(
    onSetupComplete: () -> Unit,
    viewModel: ServerSetupViewModel = hiltViewModel()
) {
    val saved by viewModel.saved.collectAsState()
    var url by remember { mutableStateOf("") }

    LaunchedEffect(saved) {
        if (saved) onSetupComplete()
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(BackgroundPrimary),
        contentAlignment = Alignment.Center
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Text(
                text = "TLEX TV",
                fontSize = 48.sp,
                fontWeight = FontWeight.Bold,
                color = TlexGold
            )

            Spacer(modifier = Modifier.height(8.dp))

            Text(
                text = "Configura il server TLEX",
                fontSize = 18.sp,
                color = TextSecondary
            )

            Spacer(modifier = Modifier.height(40.dp))

            OutlinedTextField(
                value = url,
                onValueChange = { url = it },
                label = { Text("URL Server", color = TextSecondary) },
                placeholder = { Text("es. http://192.168.1.100:8000", color = TextSecondary.copy(alpha = 0.5f)) },
                singleLine = true,
                modifier = Modifier.width(480.dp),
                shape = RoundedCornerShape(8.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedTextColor = TextPrimary,
                    unfocusedTextColor = TextPrimary,
                    focusedBorderColor = TlexGold,
                    unfocusedBorderColor = SurfaceVariant,
                    cursorColor = TlexGold,
                    focusedContainerColor = BackgroundSecondary,
                    unfocusedContainerColor = BackgroundSecondary
                ),
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Uri,
                    imeAction = ImeAction.Done
                ),
                keyboardActions = KeyboardActions(
                    onDone = { viewModel.saveServerUrl(url) }
                )
            )

            Spacer(modifier = Modifier.height(24.dp))

            Button(
                onClick = { viewModel.saveServerUrl(url) },
                modifier = Modifier.width(480.dp).height(48.dp),
                shape = RoundedCornerShape(8.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = TlexGold,
                    contentColor = BackgroundPrimary
                )
            ) {
                Text(
                    text = "Connetti",
                    fontSize = 16.sp,
                    fontWeight = FontWeight.SemiBold
                )
            }
        }
    }
}
