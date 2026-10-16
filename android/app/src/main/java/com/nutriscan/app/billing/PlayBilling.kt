package com.nutriscan.app.billing

import android.app.Activity
import android.content.Context
import com.android.billingclient.api.BillingClient
import com.android.billingclient.api.BillingClientStateListener
import com.android.billingclient.api.BillingFlowParams
import com.android.billingclient.api.BillingResult
import com.android.billingclient.api.ProductDetails
import com.android.billingclient.api.Purchase
import com.android.billingclient.api.PurchasesUpdatedListener
import com.android.billingclient.api.QueryProductDetailsParams
import com.android.billingclient.api.QueryPurchasesParams
import com.android.billingclient.api.queryProductDetails
import com.android.billingclient.api.queryPurchasesAsync
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlin.coroutines.resume

/** Product IDs must match the subscriptions in Play Console and the server's
 * PLAY_PRODUCT_PLANS. */
object ProProducts {
    const val MONTHLY = "nutriscan_pro_monthly"
    const val YEARLY = "nutriscan_pro_yearly"
    val all = listOf(MONTHLY, YEARLY)
}

data class ProPlan(val productId: String, val price: String, val details: ProductDetails, val offerToken: String)

data class PlayPurchase(val productId: String, val token: String)

sealed class PurchaseEvent {
    data class Purchased(val purchase: PlayPurchase) : PurchaseEvent()
    data object Pending : PurchaseEvent()
    data object Cancelled : PurchaseEvent()
    data class Failed(val message: String) : PurchaseEvent()
}

/** Thin wrapper over Google Play Billing. It only reports what Play says was
 * purchased -- whether that grants Pro is decided by the backend, which checks
 * the token with Google and acknowledges the purchase. */
class PlayBilling(context: Context) : PurchasesUpdatedListener {
    private val _events = MutableSharedFlow<PurchaseEvent>(extraBufferCapacity = 4)
    val events: SharedFlow<PurchaseEvent> = _events.asSharedFlow()

    private val client = BillingClient.newBuilder(context.applicationContext)
        .setListener(this)
        .enablePendingPurchases()
        .build()

    suspend fun connect(): Boolean {
        if (client.isReady) return true
        return suspendCancellableCoroutine { cont ->
            client.startConnection(object : BillingClientStateListener {
                override fun onBillingSetupFinished(result: BillingResult) {
                    if (cont.isActive) cont.resume(result.responseCode == BillingClient.BillingResponseCode.OK)
                }

                override fun onBillingServiceDisconnected() {
                    // Reconnected lazily by the next connect() call.
                }
            })
        }
    }

    suspend fun loadPlans(): List<ProPlan> {
        val params = QueryProductDetailsParams.newBuilder()
            .setProductList(
                ProProducts.all.map {
                    QueryProductDetailsParams.Product.newBuilder()
                        .setProductId(it)
                        .setProductType(BillingClient.ProductType.SUBS)
                        .build()
                },
            )
            .build()
        val result = client.queryProductDetails(params)
        return result.productDetailsList.orEmpty().mapNotNull { details ->
            val offer = details.subscriptionOfferDetails?.firstOrNull() ?: return@mapNotNull null
            val price = offer.pricingPhases.pricingPhaseList.lastOrNull()?.formattedPrice ?: return@mapNotNull null
            ProPlan(details.productId, price, details, offer.offerToken)
        }.sortedBy { ProProducts.all.indexOf(it.productId) }
    }

    /** Purchases Play already has for this account, so a reinstall or new
     * device can restore Pro by re-verifying them with the backend. */
    suspend fun ownedPurchases(): List<PlayPurchase> {
        val result = client.queryPurchasesAsync(
            QueryPurchasesParams.newBuilder().setProductType(BillingClient.ProductType.SUBS).build(),
        )
        return result.purchasesList
            .filter { it.purchaseState == Purchase.PurchaseState.PURCHASED }
            .mapNotNull { purchase -> purchase.products.firstOrNull()?.let { PlayPurchase(it, purchase.purchaseToken) } }
    }

    fun launch(activity: Activity, plan: ProPlan) {
        val params = BillingFlowParams.newBuilder()
            .setProductDetailsParamsList(
                listOf(
                    BillingFlowParams.ProductDetailsParams.newBuilder()
                        .setProductDetails(plan.details)
                        .setOfferToken(plan.offerToken)
                        .build(),
                ),
            )
            .build()
        val result = client.launchBillingFlow(activity, params)
        if (result.responseCode != BillingClient.BillingResponseCode.OK) {
            _events.tryEmit(PurchaseEvent.Failed("Couldn't open Google Play. Please try again."))
        }
    }

    override fun onPurchasesUpdated(result: BillingResult, purchases: MutableList<Purchase>?) {
        when (result.responseCode) {
            BillingClient.BillingResponseCode.OK -> purchases.orEmpty().forEach { purchase ->
                val productId = purchase.products.firstOrNull() ?: return@forEach
                _events.tryEmit(
                    when (purchase.purchaseState) {
                        Purchase.PurchaseState.PURCHASED ->
                            PurchaseEvent.Purchased(PlayPurchase(productId, purchase.purchaseToken))
                        else -> PurchaseEvent.Pending
                    },
                )
            }
            BillingClient.BillingResponseCode.USER_CANCELED -> _events.tryEmit(PurchaseEvent.Cancelled)
            BillingClient.BillingResponseCode.ITEM_ALREADY_OWNED ->
                _events.tryEmit(PurchaseEvent.Failed("You already have this subscription -- reopen this screen to restore it."))
            else -> _events.tryEmit(PurchaseEvent.Failed("The purchase didn't go through. You haven't been charged."))
        }
    }

    fun disconnect() {
        client.endConnection()
    }
}
