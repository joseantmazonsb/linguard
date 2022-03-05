using System.Linq.Expressions;

namespace Linguard.Core.Utils.Extensions; 

public static class EnumerableExtensions {
    
    /// <summary>
    /// Returns a copy of the given collection but with all instances of <c>oldValue</c> replaced by <c>newValue</c>.  
    /// </summary>
    /// <param name="enumerable"></param>
    /// <param name="oldValue"></param>
    /// <param name="newValue"></param>
    /// <typeparam name="T"></typeparam>
    /// <returns></returns>
    /// <exception cref="ArgumentException"></exception>
    public static IEnumerable<T> Replace<T>(this ICollection<T> enumerable, T oldValue, T newValue) {
        if (!enumerable.Contains(oldValue)) {
            throw new ArgumentException("The value to be replaced does not exist!");
        }
        var newList = (ICollection<T>) Activator.CreateInstance(enumerable.GetType())!;
        foreach (var elem in enumerable) {
            if (!oldValue.Equals(elem)) {
                newList.Add(elem);
                continue;
            }
            newList.Add(newValue);
        }
        return newList;
    }
    
    public static IEnumerable<T> Replace<T>(this ICollection<T> enumerable, Expression<Func<T, bool>> predicate, T newValue) {
        var newList = (ICollection<T>) Activator.CreateInstance(enumerable.GetType())!;
        foreach (var elem in enumerable) {
            if (!predicate.Compile().Invoke(elem)) {
                newList.Add(elem);
                continue;
            }
            newList.Add(newValue);
        }
        return newList;
    }
}