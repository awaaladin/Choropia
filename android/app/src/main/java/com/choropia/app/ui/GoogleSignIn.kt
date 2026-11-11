package com.choropia.app.ui

import android.content.Context
import androidx.credentials.CredentialManager
import androidx.credentials.CustomCredential
import androidx.credentials.GetCredentialRequest
import androidx.credentials.exceptions.GetCredentialCancellationException
import androidx.credentials.exceptions.GetCredentialException
import androidx.credentials.exceptions.NoCredentialException
import com.google.android.libraries.identity.googleid.GetSignInWithGoogleOption
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential

/** What came back from the Google account picker. */
sealed interface GoogleResult {
    data class Token(val idToken: String) : GoogleResult
    data object Cancelled : GoogleResult
    data class Failed(val message: String) : GoogleResult
}

/** Opens Android's own "Continue with Google" sheet and returns a Google ID token for the server to verify. */
suspend fun requestGoogleIdToken(context: Context, webClientId: String): GoogleResult {
    // The explicit "Sign in with Google" sheet: it lets the person pick or add any Google account on the phone.
    val option = GetSignInWithGoogleOption.Builder(webClientId).build()
    val request = GetCredentialRequest.Builder().addCredentialOption(option).build()
    return try {
        val credential = CredentialManager.create(context).getCredential(context, request).credential
        if (credential is CustomCredential && credential.type == GoogleIdTokenCredential.TYPE_GOOGLE_ID_TOKEN_CREDENTIAL) {
            GoogleResult.Token(GoogleIdTokenCredential.createFrom(credential.data).idToken)
        } else {
            GoogleResult.Failed("Google sign-in returned something unexpected.")
        }
    } catch (e: GetCredentialCancellationException) {
        GoogleResult.Cancelled
    } catch (e: NoCredentialException) {
        GoogleResult.Failed("No Google account was found on this phone. Add one in Settings, then try again.")
    } catch (e: GetCredentialException) {
        // Say what really went wrong, so it can be fixed instead of guessed at.
        val kind = e.type.substringAfterLast('.').ifBlank { e::class.java.simpleName }
        GoogleResult.Failed("Google sign-in couldn't start ($kind): ${e.message ?: "no more detail"}")
    }
}
