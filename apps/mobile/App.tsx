import { ChangeEvent, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Button,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  Platform,
  View,
} from "react-native";
import { QueryClient, QueryClientProvider, useMutation } from "@tanstack/react-query";
import * as ImagePicker from "expo-image-picker";
import { StatusBar } from "expo-status-bar";
import Constants from "expo-constants";
import axios from "axios";

type FieldType =
  | "text"
  | "textarea"
  | "checkbox"
  | "select"
  | "date"
  | "signature"
  | "table";

type FormField = {
  id: string;
  label: string;
  type: FieldType;
  required: boolean;
  placeholder?: string;
  options?: string[];
  bounding_box?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  metadata?: Record<string, unknown>;
};

type FormDocument = {
  form_id: string;
  title: string;
  description?: string;
  version: string;
  created_at: string;
  source_image_url?: string;
  fields: FormField[];
};

type ExtractionResponse = {
  document: FormDocument;
};

const queryClient = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <StatusBar style="auto" />
      <Root />
    </QueryClientProvider>
  );
}

function Root() {
  const backendUrl = Constants.expoConfig?.extra?.backendUrl ?? "http://localhost:8000";
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const [document, setDocument] = useState<FormDocument | null>(null);
  const [formValues, setFormValues] = useState<Record<string, string | boolean>>({});
  const [submittedData, setSubmittedData] = useState<
    Array<{ id: string; label: string; value: string | boolean }>
  >([]);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const mutation = useMutation({
    mutationFn: async (formData: FormData) => {
      const response = await axios.post<ExtractionResponse>(`${backendUrl}/extract`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      return response.data.document;
    },
    onSuccess: (data) => {
      setDocument(data);
      setSubmittedData([]);
      const defaults = data.fields.reduce<Record<string, string | boolean>>((acc, field) => {
        acc[field.id] = field.type === "checkbox" ? false : "";
        return acc;
      }, {});
      setFormValues(defaults);
    },
    onError: (error) => {
      console.error(error);
      Alert.alert("Extraction failed", "Unable to process the form. Please try again.");
    },
  });

  const handlePickImage = async () => {
    if (Platform.OS === "web") {
      Alert.alert("Not supported", "Use Upload Photo when running on the web.");
      return;
    }

    const permission = await ImagePicker.requestCameraPermissionsAsync();
    if (!permission.granted) {
      Alert.alert("Permission required", "Camera access is needed to capture the form.");
      return;
    }
    const result = await ImagePicker.launchCameraAsync({
      allowsEditing: false,
      quality: 0.8,
      base64: false,
    });

    if (!result.canceled && result.assets.length > 0) {
      const asset = result.assets[0];
      setSelectedImage(asset.uri);
      const formData = new FormData();
      const fileExtension = asset.uri.split(".").pop() ?? "jpg";
      formData.append("file", {
        uri: asset.uri,
        name: `form.${fileExtension}`,
        type: `image/${fileExtension}`,
      } as any);
      mutation.mutate(formData);
    }
  };

  const handleSelectImage = async () => {
    if (Platform.OS === "web") {
      fileInputRef.current?.click();
      return;
    }

    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      Alert.alert("Permission required", "Library access is needed to upload the form.");
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      allowsEditing: false,
      quality: 0.8,
      base64: false,
    });

    if (!result.canceled && result.assets.length > 0) {
      const asset = result.assets[0];
      setSelectedImage(asset.uri);
      const formData = new FormData();
      const fileExtension = asset.uri.split(".").pop() ?? "jpg";
      formData.append("file", {
        uri: asset.uri,
        name: `form.${fileExtension}`,
        type: `image/${fileExtension}`,
      } as any);
      mutation.mutate(formData);
    }
  };

  const handleWebFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    const previewUrl = URL.createObjectURL(file);
    setSelectedImage(previewUrl);

    const formData = new FormData();
    formData.append("file", file);
    mutation.mutate(formData);

    event.target.value = "";
  };

  const handleInputChange = (fieldId: string, value: string | boolean) => {
    setFormValues((prev) => ({ ...prev, [fieldId]: value }));
  };

  const handleSubmit = () => {
    if (!document) return;
    const summary = document.fields.map((field) => ({
      id: field.id,
      label: field.label,
      value: formValues[field.id] ?? (field.type === "checkbox" ? false : ""),
    }));
    setSubmittedData(summary);
  };

  const hasSubmission = submittedData.length > 0;

  const renderField = (field: FormField) => {
    switch (field.type) {
      case "checkbox":
        const isChecked = Boolean(formValues[field.id]);
        return (
          <View key={field.id} style={styles.checkboxContainer}>
            <Pressable
              onPress={() => handleInputChange(field.id, !isChecked)}
              style={[styles.checkboxPlaceholder, isChecked && styles.checkboxActive]}
            >
              {isChecked && <Text style={styles.checkboxMark}>✓</Text>}
            </Pressable>
            <Text style={styles.fieldLabel}>
              {field.label}
              {field.required ? " *" : ""}
            </Text>
          </View>
        );
      case "textarea":
        return (
          <View key={field.id} style={styles.fieldContainer}>
            <Text style={styles.fieldLabel}>
              {field.label}
              {field.required ? " *" : ""}
            </Text>
            <TextInput
              multiline
              numberOfLines={4}
              style={[styles.textInput, styles.textarea]}
              placeholder={field.placeholder ?? "Enter text"}
              value={String(formValues[field.id] ?? "")}
              onChangeText={(text) => handleInputChange(field.id, text)}
            />
          </View>
        );
      case "select":
        return (
          <View key={field.id} style={styles.fieldContainer}>
            <Text style={styles.fieldLabel}>
              {field.label}
              {field.required ? " *" : ""}
            </Text>
            <View style={styles.select}>
              <Text style={styles.selectPlaceholder}>
                {String(formValues[field.id] || "Tap to choose")}
              </Text>
            </View>
            {field.options && field.options.length > 0 && (
              <Text style={styles.helperText}>Options: {field.options.join(", ")}</Text>
            )}
          </View>
        );
      case "table":
        return (
          <View key={field.id} style={styles.fieldContainer}>
            <Text style={styles.fieldLabel}>{field.label}</Text>
            <Text style={styles.helperText}>Table editing not yet supported.</Text>
          </View>
        );
      case "signature":
        return (
          <View key={field.id} style={styles.fieldContainer}>
            <Text style={styles.fieldLabel}>{field.label}</Text>
            <View style={styles.signaturePlaceholder} />
          </View>
        );
      case "date":
      case "text":
      default:
        return (
          <View key={field.id} style={styles.fieldContainer}>
            <Text style={styles.fieldLabel}>
              {field.label}
              {field.required ? " *" : ""}
            </Text>
            <TextInput
              style={styles.textInput}
              placeholder={field.placeholder ?? "Enter value"}
              value={String(formValues[field.id] ?? "")}
              onChangeText={(text) => handleInputChange(field.id, text)}
            />
          </View>
        );
    }
  };

  return (
    <View style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContainer}>
        <Text style={styles.title}>Paper Form Digitizer</Text>
        <Text style={styles.subtitle}>
          Capture a photo of a paper form and generate a digital version instantly.
        </Text>

        <View style={styles.buttonRow}>
          <Button title="Capture Form" onPress={handlePickImage} />
          <View style={styles.buttonSpacer} />
          <Button title="Upload Photo" onPress={handleSelectImage} />
        </View>

        {Platform.OS === "web" && (
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            style={{ display: "none" }}
            onChange={handleWebFileChange}
          />
        )}

        {selectedImage && (
          <Image source={{ uri: selectedImage }} style={styles.previewImage} resizeMode="contain" />
        )}

        {mutation.isPending && (
          <View style={styles.loading}>
            <ActivityIndicator size="large" />
            <Text style={styles.helperText}>Processing form with OpenAI…</Text>
          </View>
        )}

        {document && (
          <View style={styles.formContainer}>
            <Text style={styles.formTitle}>{document.title}</Text>
            {document.description && <Text style={styles.helperText}>{document.description}</Text>}
            {document.fields.map(renderField)}
            <Button title="Submit" onPress={handleSubmit} />
          </View>
        )}

        {hasSubmission && (
          <View style={styles.summaryContainer}>
            <Text style={styles.summaryTitle}>Submission Preview</Text>
            {submittedData.map((entry) => (
              <View key={entry.id} style={styles.summaryRow}>
                <Text style={styles.summaryLabel}>{entry.label}</Text>
                <Text style={styles.summaryValue}>
                  {typeof entry.value === "boolean" ? (entry.value ? "Yes" : "No") : entry.value || "—"}
                </Text>
              </View>
            ))}
          </View>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#f5f5f5",
  },
  scrollContainer: {
    padding: 16,
    gap: 16,
  },
  title: {
    fontSize: 24,
    fontWeight: "600",
  },
  subtitle: {
    fontSize: 16,
    color: "#555",
  },
  buttonRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  buttonSpacer: {
    width: 12,
  },
  previewImage: {
    width: "100%",
    height: 220,
    borderRadius: 12,
    backgroundColor: "#ddd",
  },
  loading: {
    alignItems: "center",
    gap: 8,
  },
  formContainer: {
    backgroundColor: "#fff",
    padding: 16,
    borderRadius: 12,
    gap: 12,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowOffset: { width: 0, height: 4 },
    shadowRadius: 8,
    elevation: 2,
  },
  formTitle: {
    fontSize: 20,
    fontWeight: "600",
  },
  fieldContainer: {
    gap: 6,
  },
  fieldLabel: {
    fontWeight: "500",
  },
  textInput: {
    borderWidth: 1,
    borderColor: "#ccc",
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    backgroundColor: "#fafafa",
  },
  textarea: {
    minHeight: 120,
    textAlignVertical: "top",
  },
  checkboxContainer: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  checkboxPlaceholder: {
    width: 24,
    height: 24,
    borderWidth: 1,
    borderRadius: 4,
    borderColor: "#aaa",
    backgroundColor: "#fff",
    alignItems: "center",
    justifyContent: "center",
  },
  checkboxActive: {
    backgroundColor: "#4f46e5",
    borderColor: "#4f46e5",
  },
  checkboxMark: {
    color: "#fff",
    fontWeight: "700",
  },
  select: {
    borderWidth: 1,
    borderColor: "#ccc",
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 16,
    backgroundColor: "#fafafa",
  },
  selectPlaceholder: {
    color: "#888",
  },
  helperText: {
    color: "#666",
  },
  signaturePlaceholder: {
    height: 80,
    borderBottomWidth: 1,
    borderColor: "#999",
  },
  summaryContainer: {
    backgroundColor: "#eef2ff",
    padding: 16,
    borderRadius: 12,
    gap: 12,
  },
  summaryTitle: {
    fontSize: 18,
    fontWeight: "600",
    color: "#312e81",
  },
  summaryRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 12,
  },
  summaryLabel: {
    fontWeight: "500",
    flex: 1,
    color: "#1e1b4b",
  },
  summaryValue: {
    flex: 1,
    textAlign: "right",
    color: "#312e81",
  },
});

