package com.nutriscan.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.nutriscan.app.data.model.RegisterRequest
import com.nutriscan.app.data.repository.NutriScanRepository
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

    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Text(
            if (isRegisterMode) "Create account" else "Welcome back",
            style = MaterialTheme.typography.headlineSmall,
        )
        Spacer(Modifier.height(16.dp))
        OutlinedTextField(
            value = username,
            onValueChange = { username = it },
            label = { Text("Username") },
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(8.dp))
        if (isRegisterMode) {
            OutlinedTextField(
                value = email,
                onValueChange = { email = it },
                label = { Text("Email") },
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(8.dp))
        }
        OutlinedTextField(
            value = password,
            onValueChange = { password = it },
            label = { Text("Password") },
            visualTransformation = PasswordVisualTransformation(),
            modifier = Modifier.fillMaxWidth(),
        )
        errorMessage?.let {
            Spacer(Modifier.height(8.dp))
            Text(it, color = MaterialTheme.colorScheme.error)
        }
        Spacer(Modifier.height(16.dp))
        Button(
            enabled = !isLoading,
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
        ) {
            Text(
                when {
                    isLoading -> "Please wait..."
                    isRegisterMode -> "Sign up"
                    else -> "Log in"
                },
            )
        }
        Spacer(Modifier.height(8.dp))
        TextButton(onClick = { isRegisterMode = !isRegisterMode }) {
            Text(if (isRegisterMode) "Already have an account? Log in" else "New here? Create an account")
        }
    }
}
