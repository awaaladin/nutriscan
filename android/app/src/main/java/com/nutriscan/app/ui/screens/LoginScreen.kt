package com.nutriscan.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.nutriscan.app.data.model.RegisterRequest
import com.nutriscan.app.data.repository.NutriScanRepository
import com.nutriscan.app.ui.components.AnimatedGradientBackground
import com.nutriscan.app.ui.components.NsButton
import com.nutriscan.app.ui.theme.NsCream
import com.nutriscan.app.ui.theme.NsEmerald900
import com.nutriscan.app.ui.theme.NsGold300
import kotlinx.coroutines.launch

@Composable
fun LoginScreen(
    repository: NutriScanRepository,
    defaultGoal: String,
    onAuthenticated: () -> Unit,
) {
    var isRegisterMode by remember { mutableStateOf(true) }
    var username by remember { mutableStateOf("") }
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var isLoading by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    val fieldColors = OutlinedTextFieldDefaults.colors(
        focusedTextColor = NsCream,
        unfocusedTextColor = NsCream,
        focusedBorderColor = NsGold300,
        unfocusedBorderColor = NsCream.copy(alpha = 0.4f),
        focusedLabelColor = NsGold300,
        unfocusedLabelColor = NsCream.copy(alpha = 0.7f),
        cursorColor = NsGold300,
    )

    AnimatedGradientBackground(colors = listOf(NsEmerald900, Color(0xFF123D2C), NsEmerald900)) {
        Column(
            modifier = Modifier.fillMaxSize().padding(24.dp),
            verticalArrangement = Arrangement.Center,
        ) {
            Text(
                if (isRegisterMode) "Create your account" else "Welcome back",
                style = MaterialTheme.typography.headlineSmall,
                color = NsCream,
            )
            Spacer(Modifier.height(4.dp))
            Text(
                if (isRegisterMode) "Start scanning smarter in seconds." else "Good to see you again.",
                style = MaterialTheme.typography.bodyMedium,
                color = NsCream.copy(alpha = 0.7f),
            )
            Spacer(Modifier.height(24.dp))
            OutlinedTextField(
                value = username,
                onValueChange = { username = it },
                label = { Text("Username") },
                singleLine = true,
                colors = fieldColors,
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(12.dp))
            if (isRegisterMode) {
                OutlinedTextField(
                    value = email,
                    onValueChange = { email = it },
                    label = { Text("Email") },
                    singleLine = true,
                    colors = fieldColors,
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(12.dp))
            }
            OutlinedTextField(
                value = password,
                onValueChange = { password = it },
                label = { Text("Password") },
                singleLine = true,
                visualTransformation = PasswordVisualTransformation(),
                colors = fieldColors,
                modifier = Modifier.fillMaxWidth(),
            )
            errorMessage?.let {
                Spacer(Modifier.height(12.dp))
                Text(it, color = MaterialTheme.colorScheme.error)
            }
            Spacer(Modifier.height(24.dp))
            NsButton(
                enabled = !isLoading,
                text = when {
                    isLoading -> "Please wait…"
                    isRegisterMode -> "Sign up"
                    else -> "Log in"
                },
                onClick = {
                    errorMessage = null
                    isLoading = true
                    scope.launch {
                        val result = if (isRegisterMode) {
                            repository.register(RegisterRequest(username, email, password, primary_goal = defaultGoal))
                                .map { }
                        } else {
                            repository.login(username, password).map { }
                        }
                        isLoading = false
                        result.onSuccess { onAuthenticated() }
                            .onFailure { errorMessage = it.message ?: "Something went wrong" }
                    }
                },
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(8.dp))
            TextButton(onClick = { isRegisterMode = !isRegisterMode }) {
                Text(
                    if (isRegisterMode) "Already have an account? Log in" else "New here? Create an account",
                    color = NsGold300,
                )
            }
        }
    }
}
