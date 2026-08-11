using System;
using System.Collections.Generic;
using GameFactory.Core;
using UnityEngine;
#if UNITY_PURCHASING
using UnityEngine.Purchasing;
#endif

namespace GameFactory.IAP
{
    /// <summary>
    /// IAP product type (mirrors UnityEngine.Purchasing.ProductType).
    /// </summary>
    public enum IapProductType { Consumable, NonConsumable, Subscription }

    /// <summary>
    /// IAP facade. Delegates to Unity IAP (UnityEngine.Purchasing) when present.
    /// Product IDs are supplied by LaunchForge's IAP config inside the consuming project
    /// (config_generator emits iap.products from product.yaml). The real store path compiles
    /// ONLY when UNITY_PURCHASING is defined and the com.unity.purchasing package is installed;
    /// the installer enables the define + injects the Unity.Purchasing assembly reference.
    /// </summary>
    public static class IAPManager
    {
        private static bool _enabled;
        private static IapConfig _cfg;
        private static readonly List<(string id, IapProductType type)> _catalog =
            new List<(string, IapProductType)>();

        /// <summary>Register a product. Call before GameFactory.Initialize() (or before Initialize here).</summary>
        public static void AddProduct(string id, IapProductType type = IapProductType.Consumable)
        {
            if (!string.IsNullOrEmpty(id)) _catalog.Add((id, type));
        }

        public static void Initialize(IapConfig cfg)
        {
            _cfg = cfg;
            _enabled = cfg?.enabled ?? false;
            _catalog.Clear();
            if (cfg?.products != null)
                foreach (var p in cfg.products)
                    _catalog.Add((p.id, ParseType(p.type)));
            Debug.Log("[IAP] enabled=" + _enabled + " catalog=" + _catalog.Count);
#if UNITY_PURCHASING
            if (_enabled) IapListener.Ensure(_catalog);
#else
            if (_enabled)
                Debug.LogWarning("[IAP] Unity IAP not present; define UNITY_PURCHASING + install com.unity.purchasing to enable purchases.");
#endif
        }

        public static void Purchase(string productId)
        {
            if (!_enabled) return;
#if UNITY_PURCHASING
            IapListener.Instance?.Buy(productId);
#else
            Debug.Log("[IAP] Purchase " + productId + " (no store backend)");
#endif
        }

        public static void Restore()
        {
#if UNITY_PURCHASING
            IapListener.Instance?.Restore();
#else
            Debug.Log("[IAP] Restore (no store backend)");
#endif
        }

        private static IapProductType ParseType(string raw) => raw?.ToLowerInvariant() switch
        {
            "non_consumable" => IapProductType.NonConsumable,
            "subscription"   => IapProductType.Subscription,
            _                => IapProductType.Consumable
        };

#if UNITY_PURCHASING
        private sealed class IapListener : IStoreListener
        {
            private static IapListener _instance;
            public static IapListener Instance => _instance;

            private IStoreController _controller;
            private IAppleExtensions _apple;

            public static void Ensure(IReadOnlyList<(string id, IapProductType type)> catalog)
            {
                if (_instance != null) return;
                _instance = new IapListener();
                var builder = ConfigurationBuilder.Instance(StandardPurchasingModule.Instance());
                foreach (var (id, type) in catalog)
                    builder.AddProduct(id, ToUnityType(type));
                UnityPurchasing.Initialize(_instance, builder);
                Debug.Log("[IAP] Unity IAP initializing with " + catalog.Count + " products");
            }

            public void OnInitialized(IStoreController controller, IExtensionProvider extensions)
            {
                _controller = controller;
                _apple = extensions.GetExtension<IAppleExtensions>();
                Debug.Log("[IAP] initialized; products=" + controller.products.all.Length);
            }

            public void OnInitializeFailed(InitializationFailureReason reason) =>
                Debug.LogError("[IAP] init failed: " + reason);

            public void OnInitializeFailed(InitializationFailureReason reason, string message) =>
                Debug.LogError("[IAP] init failed: " + reason + " " + message);

            public PurchaseProcessingResult ProcessPurchase(PurchaseEventArgs e)
            {
                Debug.Log("[IAP] purchased: " + e.purchasedProduct.definition.id);
                // TODO: fulfill via LaunchForge server-side receipt validation + grant entitlements.
                return PurchaseProcessingResult.Complete;
            }

            public void OnPurchaseFailed(Product product, PurchaseFailureReason reason) =>
                Debug.LogError("[IAP] purchase failed: " + product.definition.id + " " + reason);

            public void Buy(string id) => _controller?.InitiatePurchase(id);

            public void Restore() => _apple?.RestoreTransactions(null);

            private static ProductType ToUnityType(IapProductType t) => t switch
            {
                IapProductType.NonConsumable => ProductType.NonConsumable,
                IapProductType.Subscription   => ProductType.Subscription,
                _                             => ProductType.Consumable
            };
        }
#endif
    }
}
