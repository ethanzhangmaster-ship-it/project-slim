using System;
using System.Collections.Generic;

namespace GameFactory.Core
{
    /// <summary>
    /// Minimal service locator. GameFactory registers its core services here so that
    /// cross-module code (e.g. analytics reading the current user id) can resolve them
    /// without a hard dependency chain. Keyed by type.
    /// </summary>
    public static class ServiceLocator
    {
        private static readonly Dictionary<Type, object> Services = new Dictionary<Type, object>();

        public static void Set<T>(T service) where T : class
        {
            if (service == null) return;
            Services[typeof(T)] = service;
        }

        public static T Get<T>() where T : class
        {
            return Services.TryGetValue(typeof(T), out var s) ? s as T : null;
        }

        public static bool Has<T>() where T : class => Services.ContainsKey(typeof(T));

        public static void Clear() => Services.Clear();
    }
}
