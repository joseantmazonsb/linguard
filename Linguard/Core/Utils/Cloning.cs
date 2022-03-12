namespace Linguard.Core.Utils; 

public static class Cloning {
    
    /// <summary>
    /// Clone an object with properties that implement <c>ICloneable</c>.
    /// </summary>
    /// <remarks>Properties that do not implement <c>ICloneable</c> won't be cloned.</remarks>
    /// <remarks>The type must have a parameterless constructor.</remarks>
    /// <param name="original"></param>
    /// <typeparam name="T"></typeparam>
    /// <returns></returns>
    public static T Clone<T>(T original) where T : new() {
        return Clone<T, T>(original);
    }

    public static TI Clone<TI, TC>(TI original) where TC : TI {
        TI clone = Activator.CreateInstance<TC>();
        var cloneableProperties = original!.GetType().GetProperties()
            .Where(p => p.PropertyType.GetInterfaces().Contains(typeof(ICloneable)));
        foreach (var property in cloneableProperties) {
            var propertyValue = property.GetValue(original);
            var propertyClone = propertyValue?.GetType().GetMethod(nameof(Clone))
                !.Invoke(propertyValue, Array.Empty<object>());
            property.SetValue(clone, propertyClone);
        }
        return clone;
    }

}