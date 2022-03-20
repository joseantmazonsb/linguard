using Linguard.Core.Configuration;
using Linguard.Core.Configuration.Serialization;
using YamlDotNet.Core;
using YamlDotNet.Serialization;

namespace Linguard.Yaml.Serialization; 

public class YamlConfigurationSerializerBuilder {
    private readonly DeserializerBuilder _deserializerBuilder = new();
    private readonly SerializerBuilder _serializerBuilder = new();

    public YamlConfigurationSerializerBuilder WithTagMapping<T>(TagName tag) {
        _deserializerBuilder.WithTagMapping(tag, typeof(T));
        _serializerBuilder.WithTagMapping(tag, typeof(T));
        return this;
    }

    public YamlConfigurationSerializerBuilder WithNamingConvention(INamingConvention namingConvention) {
        _deserializerBuilder.WithNamingConvention(namingConvention);
        _serializerBuilder.WithNamingConvention(namingConvention);
        return this;
    }
    
    public YamlConfigurationSerializerBuilder WithTypeConverter(IYamlTypeConverter converter) {
        _deserializerBuilder.WithTypeConverter(converter);
        _serializerBuilder.WithTypeConverter(converter);
        return this;
    }
    
    public YamlConfigurationSerializerBuilder WithTypeConverter<T>() where T : IYamlTypeConverter {
        return WithTypeConverter(Activator.CreateInstance<T>());
    }
    
    public YamlConfigurationSerializerBuilder WithTypeMapping<TFrom, TTo>() where TTo : TFrom {
        _deserializerBuilder.WithTypeMapping<TFrom, TTo>();
        return this;
    }
    
    public IConfigurationSerializer Build() {
        return new YamlConfigurationSerializer(_serializerBuilder.Build(), _deserializerBuilder.Build());
    }
}