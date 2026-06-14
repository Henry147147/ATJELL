FROM mcr.microsoft.com/dotnet/sdk:10.0 AS plugin-build
WORKDIR /src
COPY AutoTranscription.slnx ./
COPY src/Jellyfin.Plugin.AutoTranscription ./src/Jellyfin.Plugin.AutoTranscription
RUN dotnet publish src/Jellyfin.Plugin.AutoTranscription/Jellyfin.Plugin.AutoTranscription.csproj \
    --configuration Release \
    --framework net9.0 \
    --output /out/AutoTranscription

FROM jellyfin/jellyfin:10.11.3
COPY --from=plugin-build /out/AutoTranscription/Jellyfin.Plugin.AutoTranscription.dll /config/plugins/AutoTranscription/Jellyfin.Plugin.AutoTranscription.dll
