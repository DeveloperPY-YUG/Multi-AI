# Configuration

Open **API Connections** to add a provider. For cloud services, enter your own API key into the native dialog, then choose **Test & refresh** and select a model. API keys are stored in Windows Credential Manager, never in the repository settings file. Model IDs and non-secret preferences persist locally. Chats remain in memory and disappear when the app closes. Cloud requests send relevant chat context to the selected provider.

Custom cloud endpoints require HTTPS and an OpenAI-compatible streaming chat API. Local endpoints are restricted to loopback. If discovery fails, add an exact model ID in **Model Manager**. Do not paste secrets into issues or project files.
