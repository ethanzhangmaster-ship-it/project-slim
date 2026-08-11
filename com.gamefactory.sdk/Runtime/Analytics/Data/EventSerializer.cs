using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;

namespace GameFactory.Analytics.Data
{
    /// <summary>
    /// Minimal, dependency-free JSON writer + reader for the flat-ish dictionaries our events
    /// produce. Intentionally tiny — supports object / array / string / number / bool / null so
    /// the offline cache round-trips without pulling in Newtonsoft or System.Text.Json.
    /// </summary>
    internal static class EventSerializer
    {
        public static string Write(Dictionary<string, object> d)
        {
            var sb = new StringBuilder();
            sb.Append('{');
            bool first = true;
            foreach (var kv in d)
            {
                if (!first) sb.Append(',');
                first = false;
                WriteValue(sb, kv.Key);
                sb.Append(':');
                WriteValue(sb, kv.Value);
            }
            sb.Append('}');
            return sb.ToString();
        }

        static void WriteValue(StringBuilder sb, object v)
        {
            if (v == null) { sb.Append("null"); return; }
            if (v is string s) { sb.Append('"'); sb.Append(Escape(s)); sb.Append('"'); return; }
            if (v is bool b) { sb.Append(b ? "true" : "false"); return; }
            if (v is double || v is float || v is decimal)
            {
                sb.Append(((IFormattable)v).ToString(null, CultureInfo.InvariantCulture));
                return;
            }
            if (v is long || v is int || v is short || v is byte)
            {
                sb.Append(((IFormattable)v).ToString(null, CultureInfo.InvariantCulture));
                return;
            }
            sb.Append('"'); sb.Append(Escape(v.ToString())); sb.Append('"');
        }

        static string Escape(string s)
        {
            var sb = new StringBuilder();
            foreach (char c in s)
            {
                switch (c)
                {
                    case '"': sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': sb.Append("\\r"); break;
                    case '\t': sb.Append("\\t"); break;
                    default:
                        if (c < 0x20) sb.Append("\\u").Append(((int)c).ToString("x4"));
                        else sb.Append(c);
                        break;
                }
            }
            return sb.ToString();
        }

        public static Dictionary<string, object> Read(string line)
        {
            int i = 0;
            return ParseObject(line, ref i);
        }

        /// <summary>Serializes a list of event dicts as a compact JSON array (for HTTP upload).</summary>
        public static string WriteBatch(List<Dictionary<string, object>> batch)
        {
            var sb = new StringBuilder();
            sb.Append('[');
            bool first = true;
            foreach (var d in batch)
            {
                if (!first) sb.Append(',');
                first = false;
                WriteValue(sb, d);
            }
            sb.Append(']');
            return sb.ToString();
        }

        static Dictionary<string, object> ParseObject(string s, ref int i)
        {
            var d = new Dictionary<string, object>();
            SkipWs(s, ref i);
            if (i >= s.Length || s[i] != '{') return d;
            i++;
            SkipWs(s, ref i);
            if (i < s.Length && s[i] == '}') { i++; return d; }
            while (i < s.Length)
            {
                SkipWs(s, ref i);
                var key = ParseString(s, ref i);
                SkipWs(s, ref i);
                if (i < s.Length && s[i] == ':') i++;
                SkipWs(s, ref i);
                var val = ParseValue(s, ref i);
                d[key] = val;
                SkipWs(s, ref i);
                if (i < s.Length && s[i] == ',') { i++; continue; }
                if (i < s.Length && s[i] == '}') { i++; break; }
                break;
            }
            return d;
        }

        static object ParseValue(string s, ref int i)
        {
            SkipWs(s, ref i);
            if (i >= s.Length) return null;
            char c = s[i];
            if (c == '"') return ParseString(s, ref i);
            if (c == '{') return ParseObject(s, ref i);
            if (c == '[') return ParseArray(s, ref i);
            if (c == 't' || c == 'f') return ParseBool(s, ref i);
            if (c == 'n') { i += 4; return null; }
            return ParseNumber(s, ref i);
        }

        static string ParseString(string s, ref int i)
        {
            i++; // opening quote
            var sb = new StringBuilder();
            while (i < s.Length)
            {
                char c = s[i++];
                if (c == '"') break;
                if (c == '\\' && i < s.Length)
                {
                    char e = s[i++];
                    switch (e)
                    {
                        case '"': sb.Append('"'); break;
                        case '\\': sb.Append('\\'); break;
                        case '/': sb.Append('/'); break;
                        case 'n': sb.Append('\n'); break;
                        case 'r': sb.Append('\r'); break;
                        case 't': sb.Append('\t'); break;
                        case 'u':
                            string hex = s.Substring(i, 4); i += 4;
                            sb.Append((char)Convert.ToInt32(hex, 16));
                            break;
                        default: sb.Append(e); break;
                    }
                }
                else sb.Append(c);
            }
            return sb.ToString();
        }

        static bool ParseBool(string s, ref int i)
        {
            if (s[i] == 't') { i += 4; return true; }
            i += 5; return false;
        }

        static object ParseNumber(string s, ref int i)
        {
            int start = i;
            while (i < s.Length && (char.IsDigit(s[i]) || s[i] == '.' || s[i] == '-' ||
                                    s[i] == '+' || s[i] == 'e' || s[i] == 'E')) i++;
            string num = s.Substring(start, i - start);
            if (num.Contains(".") || num.Contains("e") || num.Contains("E"))
                return double.Parse(num, CultureInfo.InvariantCulture);
            return long.Parse(num, CultureInfo.InvariantCulture);
        }

        static List<object> ParseArray(string s, ref int i)
        {
            var list = new List<object>();
            i++;
            SkipWs(s, ref i);
            if (i < s.Length && s[i] == ']') { i++; return list; }
            while (i < s.Length)
            {
                list.Add(ParseValue(s, ref i));
                SkipWs(s, ref i);
                if (i < s.Length && s[i] == ',') { i++; continue; }
                if (i < s.Length && s[i] == ']') { i++; break; }
                break;
            }
            return list;
        }

        static void SkipWs(string s, ref int i)
        {
            while (i < s.Length && (s[i] == ' ' || s[i] == '\t' || s[i] == '\n' || s[i] == '\r')) i++;
        }
    }
}
