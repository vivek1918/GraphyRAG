import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, File, X, CheckCircle, AlertCircle } from 'lucide-react';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from './ui/card';
import { uploadFiles } from '../lib/api';

const FileUpload = ({ onUploadSuccess }) => {
  const [selectedType, setSelectedType] = useState('pdf');
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);

  const fileTypes = [
    { value: 'pdf', label: 'PDF Documents', accept: { 'application/pdf': ['.pdf'] } },
    { value: 'audio', label: 'Audio Files', accept: { 'audio/*': ['.mp3', '.wav', '.m4a'] } },
    { value: 'image', label: 'Image Files', accept: { 'image/*': ['.jpg', '.png', '.gif'] } },
    { value: 'video', label: 'Video Files', accept: { 'video/*': ['.mp4', '.avi', '.mov'] } },
    { value: 'text', label: 'Text Files', accept: { 'text/*': ['.txt', '.md', '.json'] } },
  ];

  const currentType = fileTypes.find(t => t.value === selectedType);

  const onDrop = useCallback((acceptedFiles) => {
    setFiles(prev => [...prev, ...acceptedFiles]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: currentType.accept,
  });

  const removeFile = (index) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (files.length === 0) return;

    setUploading(true);
    setUploadStatus(null);

    try {
      const result = await uploadFiles(files, selectedType);
      setUploadStatus({
        success: true,
        message: result.message,
        uploadedCount: result.uploaded_files.length,
        failedCount: result.failed_files.length,
      });
      setFiles([]);
      onUploadSuccess?.();
    } catch (error) {
      setUploadStatus({
        success: false,
        message: error.response?.data?.detail || 'Upload failed',
      });
    } finally {
      setUploading(false);
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Upload Files</CardTitle>
        <CardDescription>
          Upload multi-modal files to build your knowledge graph
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* File Type Selector */}
        <div className="flex space-x-2">
          {fileTypes.map((type) => (
            <Button
              key={type.value}
              variant={selectedType === type.value ? 'default' : 'outline'}
              size="sm"
              onClick={() => setSelectedType(type.value)}
            >
              {type.label}
            </Button>
          ))}
        </div>

        {/* Dropzone */}
        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
            isDragActive
              ? 'border-primary bg-primary/5'
              : 'border-muted-foreground/25 hover:border-muted-foreground/50'
          }`}
        >
          <input {...getInputProps()} />
          <Upload className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
          {isDragActive ? (
            <p className="text-sm">Drop the files here...</p>
          ) : (
            <div>
              <p className="text-sm mb-1">
                Drag & drop {currentType.label.toLowerCase()} here, or click to select
              </p>
              <p className="text-xs text-muted-foreground">
                Supported: {Object.values(currentType.accept)[0].join(', ')}
              </p>
            </div>
          )}
        </div>

        {/* Selected Files */}
        {files.length > 0 && (
          <div className="space-y-2">
            <p className="text-sm font-medium">Selected Files ({files.length})</p>
            <div className="space-y-1 max-h-40 overflow-y-auto">
              {files.map((file, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between p-2 bg-muted rounded-md text-sm"
                >
                  <div className="flex items-center space-x-2 flex-1 min-w-0">
                    <File className="h-4 w-4 flex-shrink-0" />
                    <span className="truncate">{file.name}</span>
                    <span className="text-muted-foreground text-xs">
                      {formatFileSize(file.size)}
                    </span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => removeFile(index)}
                    className="h-6 w-6 p-0"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Upload Status */}
        {uploadStatus && (
          <div
            className={`flex items-center space-x-2 p-3 rounded-md ${
              uploadStatus.success
                ? 'bg-green-500/10 text-green-600 dark:text-green-400'
                : 'bg-red-500/10 text-red-600 dark:text-red-400'
            }`}
          >
            {uploadStatus.success ? (
              <CheckCircle className="h-5 w-5" />
            ) : (
              <AlertCircle className="h-5 w-5" />
            )}
            <div className="flex-1 text-sm">
              <p>{uploadStatus.message}</p>
              {uploadStatus.success && uploadStatus.uploadedCount > 0 && (
                <p className="text-xs mt-1">
                  {uploadStatus.uploadedCount} file(s) uploaded successfully
                  {uploadStatus.failedCount > 0 && `, ${uploadStatus.failedCount} failed`}
                </p>
              )}
            </div>
          </div>
        )}

        {/* Upload Button */}
        <Button
          onClick={handleUpload}
          disabled={files.length === 0 || uploading}
          className="w-full"
        >
          {uploading ? 'Uploading...' : `Upload ${files.length} File(s)`}
        </Button>
      </CardContent>
    </Card>
  );
};

export default FileUpload;
